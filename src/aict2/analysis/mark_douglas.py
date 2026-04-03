from __future__ import annotations

from aict2.analysis.analysis_service import AnalysisSnapshot


def build_mark_douglas_verdict(snapshot: AnalysisSnapshot) -> str:
    if snapshot.status == 'NO TRADE':
        return (
            'Stand aside. There is no edge here that justifies action with predefined risk, '
            'so discipline means preserving capital and waiting for a cleaner opportunity.'
        )

    if snapshot.status == 'WAIT':
        return (
            'Wait with intent. The thesis may still be valid, but the entry is not mature enough yet, '
            'so discipline means not dismissing the idea and not acting before confirmation and predefined risk align.'
        )

    if snapshot.status == 'WATCH':
        return (
            'Stay observant, not impulsive. The context is useful, but it is not an invitation to act early, '
            'so keep the idea on the board and wait until the market earns your predefined risk.'
        )

    if snapshot.request.bundle_profile == 'micro':
        return (
            'This is an edge with predefined risk, but it is coming from a micro execution bundle. '
            'Take it only if you can stay precise, respect the $120 cap, and refuse to let 30-second noise '
            'pull you into over-managing the trade.'
        )

    if snapshot.request.bundle_profile == 'custom':
        return (
            'This setup may have an edge, but it comes from a custom bundle. Take it only if the thesis is still '
            'clear to you, the risk is predefined, and you are not filling in missing structure with hope.'
        )

    if snapshot.status == 'LIVE SETUP':
        return (
            'This is an edge with predefined risk. Take it only as written, '
            'accept the $120 risk, and let probabilities work without hesitation.'
        )
    return ''
