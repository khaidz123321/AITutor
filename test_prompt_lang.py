import asyncio
import sys
import os

sys.path.append(r"d:\Project\AITutor\AI")

from schemas.exercise import GenerateFromTheoryRequest
from controller.endpoints import exercises

async def main():
    req = GenerateFromTheoryRequest(
        subject="course_27",
        chapter="chuong_1"
    )
    print("=== TESTING GENERATE FROM THEORY FOR course_27 chuong_1 WITH PURE VIETNAMESE PROMPT ===")
    try:
        res = await exercises.generate_from_theory(req)
        print("\nSUCCESS!")
        print("Message:", res.message)
        print("Data count:", len(res.data))
        for i, ex in enumerate(res.data, start=1):
            print(f"\n--- EXERCISE {i} ---")
            print("Code:", ex.exerciseCode)
            print("Topic:", ex.exerciseName)
            print("Difficulty:", ex.difficulty)
            print("Bloom:", ex.bloomLevel)
            print("Question:", ex.question)
            print("CorrectAnswer:", ex.correctAnswer)
    except Exception as e:
        print("\nFAILED EXCEPTION:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
