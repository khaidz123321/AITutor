import asyncio
import os
import sys

sys.path.append(r"d:\Project\AITutor")
from AI.controller.endpoints.exercises import generate_from_theory, GenerateFromTheoryRequest

async def main():
    req = GenerateFromTheoryRequest(
        subject="course_1",
        chapter="chuong_1"
    )
    try:
        res = await generate_from_theory(req)
        print("SUCCESS!")
    except Exception as e:
        print("FAILED:", e)

if __name__ == "__main__":
    asyncio.run(main())
