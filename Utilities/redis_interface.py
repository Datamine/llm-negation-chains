import json
import re
from typing import Optional

import pandas as pd
import redis

from llm_interface import GeneralClient

REDIS_PASSWORD = None
REDIS_INSTANCE = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
    password=REDIS_PASSWORD,
    db=0,
)


class SpreadsheetRedisProcessor:
    def __init__(self, llms: list[GeneralClient]) -> None:
        """
        Initializes the processor with a Redis instance and a list of LLM objects.
        For each LLM in the list, uses LLM.model as the key in Redis.
        """
        self.redis_instance = REDIS_INSTANCE
        self.llm_models = llms

    def clear_all_locks(self) -> None:
        """
        Clears all Redis locks by deleting keys with the prefix "lock:".
        WARNING: This will delete all keys that match the "lock:*" pattern,
        so use with caution in a shared environment.
        """
        lock_keys: list[str] = self.redis_instance.keys("lock:*")
        if lock_keys:
            self.redis_instance.delete(*lock_keys)
        print(f"Cleared {len(lock_keys)} lock(s).")

    def load_questions(self, file_path: str) -> None:
        """
        Loads a spreadsheet file (CSV format) and for every entry in the "Question" column,
        creates a key (field) in the Redis hash for each LLM model.
        If a question already exists in Redis for a given model, its value is left unchanged.
        """
        df = pd.read_csv(file_path)
        if "Question" not in df.columns:
            raise ValueError("Spreadsheet must contain a 'Question' column.")  # noqa:TRY003, EM101

        questions = df["Question"].tolist()
        for question in questions:
            for model in self.llm_models:
                # hsetnx sets the field only if it does not already exist.
                self.redis_instance.hsetnx(model.model_name, question, "")
        print(
            f"Loaded {len(questions)} questions into Redis for {len(self.llm_models)} models.",
        )

    def set_answer(self, llm_model: GeneralClient, question: str, answer: str) -> None:
        """
        Sets the given question's value to the provided answer string in the specified LLM's Redis hash,
        using a Redis lock to ensure atomicity.
        """
        if llm_model not in self.llm_models:
            raise ValueError(f"LLM model '{llm_model}' not found in the list of managed LLMs.")  # noqa:TRY003,EM102

        lock_key = f"lock:{llm_model}:{question}"
        with self.redis_instance.lock(lock_key, timeout=10, blocking=True):
            # Check if the question exists in the Redis hash for the given llm_model.
            if not self.redis_instance.hexists(llm_model.model_name, question):
                raise ValueError(f"Question '{question}' not found in Redis hash for LLM model '{llm_model}'.")  # noqa:TRY003,EM102
            self.redis_instance.hset(llm_model.model_name, question, answer)

    def get_next_unprocessed_question(self, llm_model: GeneralClient) -> Optional[str]:
        """
        For a given LLM model, returns a string where:
        - question is the first question (from the Redis hash for that LLM)
            whose status is blank,

        The lock is held upon returning and must be released by the caller after processing.
        If no unprocessed question is found, returns None.
        """
        if llm_model not in self.llm_models:
            raise ValueError(f"LLM model '{llm_model.model_name}' not found in the list of managed LLMs.")  # noqa: TRY003,EM102

        # Retrieve all questions for the given LLM model.
        questions: dict[str, str] = self.redis_instance.hgetall(llm_model.model_name)
        for question, status in questions.items():
            if status == "":  # Found an unprocessed (blank) question.
                lock_key = f"lock:{llm_model}:{question}"
                try:
                    # Attempt to acquire the lock in a non-blocking manner.
                    with self.redis_instance.lock(lock_key, timeout=1, blocking=False):
                        # Double-check that the question's status is still blank.
                        current_status = self.redis_instance.hget(llm_model.model_name, question)
                        if current_status == "":
                            self.redis_instance.hset(llm_model.model_name, question, "processing")
                            return question
                except redis.exceptions.LockError:
                    # The lock wasn't acquired; continue to the next question.
                    continue
        return None

    def export_answers(self, original_file_path: str) -> None:
        """
        Loads the original spreadsheet, appends an "Answer" column by retrieving the answer
        from the Redis hash for the specified LLM model, and writes out a new spreadsheet file named
        'answers_{llm_model}.csv'.
        """
        for llm_model in self.llm_models:
            df = pd.read_csv(original_file_path)
            if "Question" not in df.columns:
                raise ValueError("Spreadsheet must contain a 'Question' column.")  # noqa:TRY003, EM101

            answers = []
            for question in df["Question"]:
                answer = self.redis_instance.hget(llm_model.model_name, question) or ""
                answers.append(answer)
            df["Answer"] = answers

            output_file = safe_filename(f"answers_{llm_model.model_name}.csv")
            df.to_csv(output_file, index=False)
            print(f"Exported answers to '{output_file}' for LLM model '{llm_model.model_name}'.")

    def stats(self) -> None:
        """
        For each LLM model, prints stats on questions stored in Redis:
         - how many have not been processed (empty string),
         - how many are currently set to "processing", and
         - how many have been processed (any other non-empty value).
        It also prints the list of questions for each model.
        """
        for model in self.llm_models:
            entries = self.redis_instance.hgetall(model.model_name)
            total = len(entries)
            not_processed = 0
            processing = 0
            processed = 0

            for val in entries.values():
                if val == "":
                    not_processed += 1
                elif val == "processing":
                    processing += 1
                else:
                    processed += 1

            print(f"--- Stats for LLM model '{model.model_name}' ---")
            print(f"Total questions: {total}")
            print(f"Not processed: {not_processed}")
            print(f"Processing: {processing}")
            print(f"Processed: {processed}")

    def clear_processing(self) -> None:
        """
        Clears all entries (sets to an empty string) that are currently marked as "processing" for all LLM models.
        """
        for model in self.llm_models:
            entries = self.redis_instance.hgetall(model.model_name)
            for key, val in entries.items():
                if val == "processing":
                    self.redis_instance.hset(model.model_name, key, "")
            print(f"Cleared all 'processing' entries for LLM model '{model.model_name}'.")

    def clear_all(self) -> None:
        """
        Clears all entries for all managed LLM models by deleting their corresponding Redis hashes.
        """
        for model in self.llm_models:
            self.redis_instance.delete(model.model_name)
            print(f"Cleared all entries for LLM model '{model.model_name}'.")


def safe_filename(filename: str) -> str:
    """
    Sanitize the filename by replacing unsafe characters with underscores.
    Only allows letters, digits, underscores, hyphens, and dots.
    """
    return re.sub(r"[^\w\-.]", "_", filename)


def print_all() -> None:
    data = {}
    for key in REDIS_INSTANCE.scan_iter("*"):
        key_type = REDIS_INSTANCE.type(key)  # type: ignore[no-untyped-call]
        if key_type == "string":
            data[key] = REDIS_INSTANCE.get(key)
        elif key_type == "hash":
            data[key] = REDIS_INSTANCE.hgetall(key)  # type: ignore[assignment]

    json_data = json.dumps(data, indent=2)
    print(json_data)


def test_redis() -> None:
    REDIS_INSTANCE.set("foo", "working!")
    print(REDIS_INSTANCE.get("foo"))


if __name__ == "__main__":
    test_redis()
