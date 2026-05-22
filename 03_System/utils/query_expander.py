#!/usr/bin/env python3
"""
🌐 Query Expander for Theology AI Lab v5.1
==========================================
3중 언어 쿼리 확장 모듈 (한국어, 영어, 독일어)
"""

import re
import logging
from typing import List, Dict, Set
from dataclasses import dataclass

logger = logging.getLogger("QueryExpander")

# 신학 용어 사전 (Korean -> English, German)
THEOLOGICAL_TERMS: Dict[str, Dict[str, List[str]]] = {
    "칭의": {
        "ko": ["칭의", "의롭다함", "칭의론"],
        "en": ["justification", "righteousness"],
        "de": ["Rechtfertigung", "Gerechtigkeit"],
    },
    "성화": {
        "ko": ["성화", "거룩하게 됨"],
        "en": ["sanctification", "holiness"],
        "de": ["Heiligung", "Heiligkeit"],
    },
    "구원": {
        "ko": ["구원", "구속"],
        "en": ["salvation", "redemption"],
        "de": ["Heil", "Erlösung"],
    },
    "은혜": {
        "ko": ["은혜", "은총"],
        "en": ["grace", "divine grace"],
        "de": ["Gnade", "Gottes Gnade"],
    },
    "믿음": {
        "ko": ["믿음", "신앙"],
        "en": ["faith", "belief"],
        "de": ["Glaube", "Vertrauen"],
    },
    "삼위일체": {
        "ko": ["삼위일체", "삼위일체론"],
        "en": ["Trinity", "triune God"],
        "de": ["Trinität", "Dreieinigkeit"],
    },
    "성령": {
        "ko": ["성령", "성신"],
        "en": ["Holy Spirit", "Spirit of God"],
        "de": ["Heiliger Geist", "Geist Gottes"],
    },
    "기독론": {
        "ko": ["기독론", "그리스도론"],
        "en": ["Christology", "doctrine of Christ"],
        "de": ["Christologie"],
    },
    "성육신": {
        "ko": ["성육신", "육화"],
        "en": ["incarnation", "Word became flesh"],
        "de": ["Inkarnation", "Menschwerdung"],
    },
    "속죄": {
        "ko": ["속죄", "대속"],
        "en": ["atonement", "expiation"],
        "de": ["Versöhnung", "Sühne"],
    },
    "부활": {
        "ko": ["부활"],
        "en": ["resurrection"],
        "de": ["Auferstehung"],
    },
    "하나님의 형상": {
        "ko": ["하나님의 형상", "이마고 데이"],
        "en": ["image of God", "imago Dei"],
        "de": ["Ebenbild Gottes", "imago Dei"],
    },
    "원죄": {
        "ko": ["원죄", "타락"],
        "en": ["original sin", "the Fall"],
        "de": ["Erbsünde", "Sündenfall"],
    },
    "교회": {
        "ko": ["교회", "에클레시아"],
        "en": ["church", "ecclesia"],
        "de": ["Kirche", "Ekklesia"],
    },
    "종말론": {
        "ko": ["종말론"],
        "en": ["eschatology", "last things"],
        "de": ["Eschatologie", "Endzeit"],
    },
    "하나님 나라": {
        "ko": ["하나님 나라", "천국"],
        "en": ["Kingdom of God", "Kingdom of Heaven"],
        "de": ["Reich Gottes", "Himmelreich"],
    },
    "계시": {
        "ko": ["계시"],
        "en": ["revelation", "divine revelation"],
        "de": ["Offenbarung"],
    },
    "바르트": {
        "ko": ["바르트", "칼 바르트"],
        "en": ["Barth", "Karl Barth"],
        "de": ["Barth", "Karl Barth"],
    },
    "본회퍼": {
        "ko": ["본회퍼", "디트리히 본회퍼"],
        "en": ["Bonhoeffer", "Dietrich Bonhoeffer"],
        "de": ["Bonhoeffer", "Dietrich Bonhoeffer"],
    },
    "루터": {
        "ko": ["루터"],
        "en": ["Luther", "Martin Luther"],
        "de": ["Luther", "Martin Luther"],
    },
    "아가페": {
        "ko": ["아가페", "사랑"],
        "en": ["agape", "love"],
        "de": ["Agape", "Liebe"],
        "grc": ["ἀγάπη"],
    },
    "로고스": {
        "ko": ["로고스", "말씀"],
        "en": ["logos", "Word"],
        "de": ["Logos", "Wort"],
        "grc": ["λόγος"],
    },
}


@dataclass
class ExpandedQuery:
    """확장된 쿼리 결과"""
    original: str
    korean: List[str]
    english: List[str]
    german: List[str]
    greek: List[str]
    matched_concepts: List[str]
    
    def get_all_unique(self) -> List[str]:
        seen: Set[str] = set()
        result = []
        for term in self.korean + self.english + self.german + self.greek:
            if term.lower() not in seen:
                seen.add(term.lower())
                result.append(term)
        return result


class QueryExpander:
    """신학 쿼리를 3중 언어로 확장"""
    
    def __init__(self, terms_dict: Dict = None):
        self.terms = terms_dict or THEOLOGICAL_TERMS
        self._build_reverse_index()
    
    def _build_reverse_index(self):
        self.reverse_index: Dict[str, str] = {}
        for concept, langs in self.terms.items():
            for lang, terms in langs.items():
                for term in terms:
                    self.reverse_index[term.lower()] = concept
    
    def expand(self, query: str) -> ExpandedQuery:
        logger.info(f"🌐 Expanding query: '{query}'")
        words = re.split(r'[\s,;]+', query)
        words = [w.strip() for w in words if w.strip()]
        
        korean, english, german, greek = [], [], [], []
        matched = []
        
        # Check full query first
        if query.lower() in self.reverse_index:
            words = [query]
        
        for word in words:
            concept = self.reverse_index.get(word.lower())
            if concept:
                matched.append(concept)
                data = self.terms[concept]
                korean.extend(data.get("ko", []))
                english.extend(data.get("en", []))
                german.extend(data.get("de", []))
                greek.extend(data.get("grc", []))
            else:
                korean.append(word)
                english.append(word)
                german.append(word)
        
        korean.insert(0, query)
        
        return ExpandedQuery(
            original=query,
            korean=list(set(korean)),
            english=list(set(english)),
            german=list(set(german)),
            greek=list(set(greek)),
            matched_concepts=list(set(matched))
        )
    
    def get_embedding_queries(self, query: str, max_q: int = 5) -> List[str]:
        exp = self.expand(query)
        queries = [query]
        if exp.english: queries.append(exp.english[0])
        if exp.german: queries.append(exp.german[0])
        seen = set()
        return [q for q in queries if not (q.lower() in seen or seen.add(q.lower()))][:max_q]


def expand_query(query: str) -> Dict[str, List[str]]:
    """편의 함수"""
    exp = QueryExpander()
    r = exp.expand(query)
    return {"korean": r.korean, "english": r.english, "german": r.german, "greek": r.greek}


def get_search_terms(query: str) -> List[str]:
    """모든 검색 용어 반환"""
    return QueryExpander().expand(query).get_all_unique()


if __name__ == "__main__":
    for q in ["칭의론", "바르트의 삼위일체론", "justification"]:
        print(f"\n🔍 '{q}' -> {expand_query(q)}")
