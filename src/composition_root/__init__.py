"""Composition root único do projeto (D2-P1-4, roadmap D-05).

Monta o grafo de dependências das fachadas em UM só lugar: a UI e as
ferramentas recebem as fachadas prontas daqui — nada de factories
espalhadas (F-15). Este pacote consome exclusivamente as `public_api`
dos módulos.
"""

from composition_root.root import build_facades

__all__ = ["build_facades"]
