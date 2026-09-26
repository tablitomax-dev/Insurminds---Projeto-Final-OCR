"""Adapters reais do módulo policy_analysis (duckdb, Pydantic AI/Gemini).

As libs externas são importadas de forma lazy: só falham na instanciação,
com `RuntimeError("dependência ausente: ...")`.
"""
