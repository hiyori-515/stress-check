"""
厚労省 総合健康リスク計算
判定図(A)：量的負荷×コントロール
判定図(B)：上司支援×同僚支援
総合健康リスク = A × B / 100（全国平均=100）
"""

RISK_A = {
    (1,4):76,(2,4):76,(3,4):76,(4,4):76,(5,4):79,
    (1,3):76,(2,3):76,(3,3):79,(4,3):88,(5,3):100,
    (1,2):76,(2,2):88,(3,2):100,(4,2):119,(5,2):134,
    (1,1):79,(2,1):100,(3,1):119,(4,1):134,(5,1):134,
}
RISK_B = {
    (1,1):136,(1,2):119,(1,3):108,(1,4):108,
    (2,1):119,(2,2):108,(2,3):108,(2,4):100,
    (3,1):108,(3,2):108,(3,3):100,(3,4):88,
    (4,1):108,(4,2):100,(4,3):88,(4,4):76,
}

def _cls_a(q, c):
    qc = 5 if q>=12 else 4 if q>=10 else 3 if q>=8 else 2 if q>=6 else 1
    cc = 1 if c<=4  else 2 if c<=7  else 3 if c<=9  else 4
    return qc, cc

def _cls_b(s, co):
    sc = 1 if s<=4  else 2 if s<=6  else 3 if s<=8  else 4
    cc = 1 if co<=5 else 2 if co<=7 else 3 if co<=9 else 4
    return sc, cc

def calc_health_risk(responses: dict) -> dict:
    q  = responses.get(1,3)+responses.get(2,3)+responses.get(3,3)
    c  = responses.get(8,3)+responses.get(9,3)+responses.get(10,3)
    s  = responses.get(47,3)+responses.get(50,3)+responses.get(53,3)
    co = responses.get(48,3)+responses.get(51,3)+responses.get(54,3)
    ra = RISK_A.get(_cls_a(q,c), 100)
    rb = RISK_B.get(_cls_b(s,co), 100)
    return {
        "risk_a": ra, "risk_b": rb,
        "total_risk": round(ra*rb/100),
        "quantity_sum": q, "control_sum": c,
        "supervisor_sum": s, "coworker_sum": co,
    }

def calc_group_health_risk(responses_list: list) -> dict:
    """複数人の平均から集団の健康リスクを計算"""
    import statistics
    if not responses_list:
        return {"risk_a":100,"risk_b":100,"total_risk":100,
                "quantity_mean":0,"control_mean":0,
                "supervisor_mean":0,"coworker_mean":0}
    indiv = [calc_health_risk(r) for r in responses_list]
    q_mean  = statistics.mean(r["quantity_sum"]  for r in indiv)
    c_mean  = statistics.mean(r["control_sum"]   for r in indiv)
    s_mean  = statistics.mean(r["supervisor_sum"] for r in indiv)
    co_mean = statistics.mean(r["coworker_sum"]  for r in indiv)
    # 平均値で判定図を引く
    avg_resp = {1:q_mean/3, 2:q_mean/3, 3:q_mean/3,
                8:c_mean/3, 9:c_mean/3, 10:c_mean/3,
                47:s_mean/3, 50:s_mean/3, 53:s_mean/3,
                48:co_mean/3, 51:co_mean/3, 54:co_mean/3}
    # 整数に丸めて計算
    avg_int = {k: round(v) for k,v in avg_resp.items()}
    result = calc_health_risk(avg_int)
    result.update({
        "quantity_mean": round(q_mean,1),
        "control_mean":  round(c_mean,1),
        "supervisor_mean": round(s_mean,1),
        "coworker_mean": round(co_mean,1),
    })
    return result
