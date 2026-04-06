from dotenv import load_dotenv
load_dotenv()

import asyncio

from app.runner import run_full_workflow
from app.runtime import configure_client, ensure_api_key
from app.storage import create_run_id


async def main() -> None:
    ensure_api_key()
    client = configure_client()

    run_id = create_run_id()
    workflow_result = await run_full_workflow(run_id=run_id, client=client)
    result_dirs = workflow_result["dirs"]

    print("\n===== Workflow Completed =====")
    print(f"Run ID: {run_id}")
    print(f"Research saved to: {result_dirs['research_dir']}")
    print(f"Value Trader saved to: {result_dirs['value_dir']}")
    print(f"Growth Trader saved to: {result_dirs['growth_dir']}")
    print(f"Macro Trader saved to: {result_dirs['macro_dir']}")
    print(f"Event Trader saved to: {result_dirs['event_dir']}")
    print(f"Validator saved to: {result_dirs['validator_dir']}")


if __name__ == "__main__":
    asyncio.run(main())
