"""
CodeCrew - CLI Entry Point.

Usage:
    codecrew --task "build a todo app with auth"
    codecrew --task "build a REST API" --output-dir ./my-project --human-override
"""

import os
import sys
import argparse
import warnings

# Enable UTF-8 output on Windows to support emojis
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from dotenv import load_dotenv

# Suppress annoying library warnings that pollute the terminal output
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

def run():
    """Main CLI entry point for CodeCrew."""
    parser = argparse.ArgumentParser(
        prog="codecrew",
        description="🚀 CodeCrew — Multi-Agent AI Code Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  codecrew --task "build a todo app with auth"
  codecrew --task "build a REST API with Flask" --human-override
  codecrew --task "build a CLI calculator" --output-dir ./my-project
        """,
    )

    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help='The project task description (e.g., "build a todo app with auth")',
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Directory where the generated project will be saved (default: ./output)",
    )

    parser.add_argument(
        "--human-override",
        action="store_true",
        default=False,
        help="Enable human-in-the-loop mode: use AgentScope Web UI for approval.",
    )

    args = parser.parse_args()

    # Load environment variables from .env
    load_dotenv(override=True)

    provider = os.getenv("LLM_PROVIDER", "free_ha").lower()
    print(f"\n🤖 LLM Provider: {provider}")
    print(f"🔍 Search Provider: {os.getenv('SEARCH_PROVIDER', 'duckduckgo')}")

    print(f"\n📋 Task: {args.task}")
    print(f"📁 Output: {os.path.abspath(args.output_dir)}")
    if args.human_override:
        print(f"🧑 Human Override: ENABLED (approve steps via AgentScope Studio)")
    print()

    try:
        from codecrew.pipeline import CodeCrewPipeline
        
        pipeline = CodeCrewPipeline(
            output_dir=args.output_dir,
            human_override=args.human_override,
        )
        pipeline.run(task=args.task)
        
        print(f"\n{'='*60}")
        print(f"  ✅ CodeCrew completed successfully!")
        print(f"{'='*60}")

    except KeyboardInterrupt:
        print("\n\n⚠️  CodeCrew interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ CodeCrew failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run()
