"""CLI for isolated published-peer observation replay, never policy promotion."""

import json


def run(args):
    from .published_rtc_peer import (
        audit_published_peer_replay,
        inspect_published_peer,
        list_published_peers,
        replay_published_peer,
    )

    if args.command == "rtc-peer-list":
        report = list_published_peers()
    elif args.command == "rtc-peer-inspect":
        report = inspect_published_peer(args.peer, args.checkpoint)
    elif args.command == "rtc-peer-replay":
        report = replay_published_peer(args.peer, args.checkpoint, args.trace, args.out, args.limit)
        report = {k: v for k, v in report.items() if k != "rows"}
    elif args.command == "rtc-peer-audit":
        report = audit_published_peer_replay(args.replay, args.checkpoint, args.trace)
    else:
        raise ValueError("Unknown published-peer command")
    print(json.dumps(report, indent=2, allow_nan=False))
    return report
