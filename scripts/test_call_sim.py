"""Interactive CLI telephone caller simulator for testing helpline turns."""

import asyncio
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.session import SessionLocal, init_db
from app.engine.conversation import conversation_manager


async def run_cli_simulation():
    init_db()
    db = SessionLocal()

    print("=================================================================")
    print("      RURAL AI MEDICAL HELPLINE - CLI FEATURE PHONE SIMULATOR    ")
    print("=================================================================")
    print("Dialing Helpline...")

    ctx, initial_prompt = conversation_manager.get_or_create_context(db=db)
    print(f"\n[IVR Speaker]: {initial_prompt}\n")

    while not ctx.is_completed and ctx.state.value not in ("COMPLETED", "DISCONNECTED"):
        try:
            user_input = input("Caller Keypad/Speech [1=EN, 2=HI, 3=MR, 0=Repeat, 9=End]: ").strip()
            if not user_input:
                continue

            result = await conversation_manager.process_turn(
                session_id=ctx.session_id,
                caller_input=user_input,
                is_dtmf=(user_input in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "#"]),
                db=db,
            )

            print(f"\n[IVR Response - {result.language.upper()}]:")
            print(f"{result.spoken_text}")
            if result.triage_assessment:
                print(f"[Triage Tier]: {result.triage_assessment.urgency_category.upper()}")
                print(f"[Referral Recommended]: {result.triage_assessment.referral_recommended}")
            print("-" * 65)

            if result.should_hangup or result.is_completed:
                print("\n[Call Ended]")
                break

        except (KeyboardInterrupt, EOFError):
            print("\nCaller hung up.")
            conversation_manager.disconnect_call(ctx.session_id, db=db)
            break

    db.close()


if __name__ == "__main__":
    asyncio.run(run_cli_simulation())
