from __future__ import annotations

import argparse

from ..orchestration_flow import run_group_flow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Flujo segmentado SUCAMEC")
    parser.add_argument(
        "--grupo",
        choices=["JV", "SELVA", "TODOS"],
        default="JV",
        help="Credenciales a usar para probar login.",
    )
    parser.add_argument(
        "--solo-login",
        action="store_true",
        help="Ejecuta solo el login y no navega a CONSULTAS > MIS VIGILANTES.",
    )
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    groups = ["JV", "SELVA"] if args.grupo == "TODOS" else [args.grupo]
    for group in groups:
        run_group_flow(group, solo_login=args.solo_login)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
