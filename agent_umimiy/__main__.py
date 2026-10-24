from __future__ import annotations

import argparse

from . import config
from .orchestrator import MODES


def main():
    ap = argparse.ArgumentParser(prog="agent-umimiy", description="Barcha AI agentlarni birlashtiruvchi ilova")
    ap.add_argument("-c", "--config", help="agents.json yo'li")
    ap.add_argument("-m", "--mode", choices=MODES, default="auto")
    ap.add_argument("-a", "--agents", nargs="*", help="faqat shu agentlar")
    ap.add_argument("--cli", action="store_true", help="oynasiz, terminalda ishlash")
    ap.add_argument("prompt", nargs="*", help="bir martalik so'rov (--cli bilan)")
    args = ap.parse_args()

    if not args.cli and not args.prompt:
        from . import gui

        return gui.run(args.config)

    orch = config.load(args.config)

    def ask(text):
        for r in orch.run(text, args.mode, args.agents):
            print(f"\n● {r.agent} ({r.seconds:.1f}s)")
            print(r.text if r.ok else f"Xato: {r.error}")

    if args.prompt:
        return ask(" ".join(args.prompt))
    print("Chiqish: Ctrl+D. Agentlar:", ", ".join(orch.agents))
    while True:
        try:
            text = input("\nsiz> ").strip()
        except EOFError:
            break
        if text:
            ask(text)


if __name__ == "__main__":
    main()
