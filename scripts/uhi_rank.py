from calorai.agent import AuditAgent, AuditRequest
from calorai.analyst.uhi import rank_districts
from calorai.data_source import DISTRICTS
reports=[AuditAgent(AuditRequest(district=k, date='2026-08-18', data_source='mock')).run(narrate=False) for k in sorted(DISTRICTS)]
ranked=rank_districts(reports)
for r in ranked:
    print(f"{r['rank']:2}. {r['district']:25} {r['score']:4.1f} {r['band']:8} core {r['metrics']['core_excess_k']:4.1f}K gap {r['metrics']['quintile_gap_c']:3.1f}K gini {r['metrics']['gini']:.3f} h/w {r['metrics']['h_over_w']:.1f} ret {r['metrics']['overnight_retention']:.2f}")
