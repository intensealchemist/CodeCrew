"""
CodeCrew - CLI Entry Point.

Usage:
    codecrew --task "build a todo app with auth"
    codecrew --task "build a REST API" --output-dir ./my-project --human-override
    python -m codecrew.main --task "build a CLI calculator"
"""

import os
import sys
import argparse
import warnings
import multiprocessing

# Enable UTF-8 output on Windows to support emojis
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# CRITICAL: Disable telemetry BEFORE ANY imports of crewai/litellm occur
# This MUST happen before load_dotenv and before any crewai imports
os.environ["CREWAI_DISABLE_TELEMETRY"] = "True"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "True"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["DO_NOT_TRACK"] = "True"
os.environ["OTEL_SDK_DISABLED"] = "True"

from dotenv import load_dotenv

# Suppress annoying library warnings that pollute the terminal output
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

def _run_kickoff_in_child(output_dir: str, human_override: bool, task: str):
    """Run Crew kickoff in child process to prevent parent terminal lockups."""
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    try:
        from codecrew.crew import CodeCrewCrew
        
        crew_instance = CodeCrewCrew(
            output_dir=output_dir,
            human_override=human_override,
        )
        result = crew_instance.crew().kickoff(inputs={"task": task})
        sys.stdout.flush()
        return 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        sys.exit(1)

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
        help="Enable human-in-the-loop mode: pause for approval between agents",
    )
    parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=900,
        help="Hard timeout for crew execution in seconds (default: 900).",
    )

    args = parser.parse_args()

    # Load environment variables from .env, overriding any existing system/terminal variables
    load_dotenv(override=True)

    # Validate LLM provider configuration
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    print(f"\n🤖 LLM Provider: {provider}")
    print(f"🔍 Search Provider: {os.getenv('SEARCH_PROVIDER', 'duckduckgo')}")

    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama3")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        print(f"   Model: {model}")
        print(f"   Base URL: {base_url}")
        print(f"   ⚠️  Make sure Ollama is running: ollama serve")
    elif provider == "groq":
        if not os.getenv("GROQ_API_KEY"):
            print("❌ Error: GROQ_API_KEY not set. Please set it in your .env file.")
            sys.exit(1)
        print(f"   Model: {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}")
    elif provider == "cerebras":
        if not os.getenv("CEREBRAS_API_KEY"):
            print("❌ Error: CEREBRAS_API_KEY not set. Please set it in your .env file.")
            sys.exit(1)
        print(f"   Model: {os.getenv('CEREBRAS_MODEL', 'llama-3.3-70b')}")
    elif provider == "free_ha":
        keys_found = []
        if os.getenv("GROQ_API_KEY"): keys_found.append("Groq")
        if os.getenv("CEREBRAS_API_KEY"): keys_found.append("Cerebras")
        if os.getenv("GEMINI_API_KEY"): keys_found.append("Gemini")
        if not keys_found:
            print("❌ Error: No free API keys found. Set GROQ_API_KEY, CEREBRAS_API_KEY, or GEMINI_API_KEY.")
            sys.exit(1)
        print(f"   Mode: Zero-Cost High Availability")
        print(f"   Available Fallbacks: {', '.join(keys_found)}")


    print(f"\n📋 Task: {args.task}")
    print(f"📁 Output: {os.path.abspath(args.output_dir)}")
    if args.human_override:
        print(f"🧑 Human Override: ENABLED (you'll be asked for approval)")
    print()

    try:
        proc = multiprocessing.Process(
            target=_run_kickoff_in_child,
            args=(args.output_dir, args.human_override, args.task),
            daemon=False,
        )
        proc.start()
        proc.join(timeout=args.max_runtime_seconds)

        if proc.is_alive():
            print(f"\n❌ CodeCrew timed out after {args.max_runtime_seconds}s. Terminating stuck process...")
            proc.terminate()
            proc.join(timeout=10)
            if proc.is_alive():
                proc.kill()
            sys.exit(1)

        if proc.exitcode != 0:
            raise RuntimeError(f"Crew process failed with exit code {proc.exitcode}")
        
        result = None
        print(f"\n{'='*60}")
        print(f"  ✅ CodeCrew completed successfully!")
        print(f"{'='*60}")

        return result

    except KeyboardInterrupt:
        print("\n\n⚠️  CodeCrew interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ CodeCrew failed with error: {e}")
        raise


if __name__ == "__main__":
    run()
