"""使 `python -m packages.llm.benchmark` 可运行 qualification CLI。"""

from packages.llm.benchmark.qualify import main

if __name__ == "__main__":
    raise SystemExit(main())
