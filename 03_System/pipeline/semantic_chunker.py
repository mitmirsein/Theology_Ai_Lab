#!/usr/bin/env python3
"""
🧠 Semantic Chunker for Theology AI Lab v5.1
=============================================
LLM 기반 시맨틱 청킹 모듈.

텍스트를 논리적 단위(문단, 논증, 항목)로 분리합니다.
토큰 기반 청킹보다 정밀한 검색 결과 제공.

Dual-Mode 전략:
- IDE 환경: 세션 컨텍스트 활용 (무료)
- Streamlit 배포: 별도 API 호출 (유료 ~$0.02/책)
"""

import re
import logging
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("SemanticChunker")


@dataclass
class SemanticChunk:
    """시맨틱 청크 구조"""
    content: str
    chunk_type: str  # paragraph, section, entry, argument
    start_index: int
    end_index: int
    metadata: Dict[str, Any]


class SemanticChunker:
    """
    LLM 기반 시맨틱 청킹.
    
    텍스트를 의미 단위로 분할합니다:
    - 사전: 표제어(lemma) 단위
    - 교의학: 논증/문단 단위
    - 주석: 성경 절/구 단위
    """
    
    # 구조 기반 분리 패턴
    HEADING_PATTERN = re.compile(
        r'^(?:#{1,6}\s+|(?:\d+\.)+\s+|[A-Z]\.\s+|[IVX]+\.\s+)(.+)$',
        re.MULTILINE
    )
    
    # 사전 표제어 패턴 (그리스어, 히브리어, 라틴어)
    LEMMA_PATTERN = re.compile(
        r'^([α-ωΑ-Ωἀ-ῷ]+|[א-ת]+|[a-zA-Z]+)\s*[\(\[]',
        re.MULTILINE
    )
    
    # 문단 구분자
    PARAGRAPH_SEPARATORS = ['\n\n', '\n \n', '\r\n\r\n']
    
    def __init__(self, 
                 llm_provider: str = None,
                 api_key: str = None,
                 use_structure: bool = True):
        """
        Args:
            llm_provider: LLM 제공자 (google, openai, anthropic)
            api_key: API 키 (None이면 환경변수 사용)
            use_structure: 구조 기반 분리 사용 여부
        """
        self.llm_provider = llm_provider
        self.api_key = api_key
        self.use_structure = use_structure
        self._llm = None
    
    def chunk(self, 
              text: str, 
              doc_type: str = "dogmatics",
              max_chunk_size: int = 1200,
              metadata_base: Dict[str, Any] = None) -> List[SemanticChunk]:
        """
        텍스트를 시맨틱 청크로 분할.
        
        Args:
            text: 원본 텍스트
            doc_type: 문서 유형 (dogmatics, dictionary, commentary)
            max_chunk_size: 최대 청크 크기 (토큰)
            metadata_base: 기본 메타데이터
            
        Returns:
            SemanticChunk 리스트
        """
        metadata_base = metadata_base or {}
        
        logger.info(f"🧠 Semantic chunking: {len(text)} chars, type={doc_type}")
        
        # 1. 문서 유형별 전략 선택
        if doc_type == "dictionary":
            chunks = self._chunk_dictionary(text, max_chunk_size)
        elif doc_type == "commentary":
            chunks = self._chunk_commentary(text, max_chunk_size)
        else:
            chunks = self._chunk_dogmatics(text, max_chunk_size)
        
        # 2. 메타데이터 주입
        for i, chunk in enumerate(chunks):
            chunk.metadata.update(metadata_base)
            chunk.metadata["chunk_index"] = i
            chunk.metadata["chunk_type"] = chunk.chunk_type
        
        logger.info(f"   └─ Generated {len(chunks)} chunks")
        return chunks
    
    def _chunk_dictionary(self, text: str, max_size: int) -> List[SemanticChunk]:
        """사전: 표제어 단위 분할"""
        chunks = []
        
        # 표제어 패턴으로 분할
        entries = self._split_by_lemma(text)
        
        for entry_text, lemma in entries:
            if len(entry_text.strip()) < 50:
                continue
            
            # 너무 긴 항목은 추가 분할
            if len(entry_text) > max_size * 4:
                sub_chunks = self._split_by_paragraph(entry_text, max_size)
                for j, sub in enumerate(sub_chunks):
                    chunks.append(SemanticChunk(
                        content=sub,
                        chunk_type="entry",
                        start_index=text.find(sub[:50]),
                        end_index=text.find(sub[:50]) + len(sub),
                        metadata={"lemma": lemma, "sub_index": j}
                    ))
            else:
                chunks.append(SemanticChunk(
                    content=entry_text,
                    chunk_type="entry",
                    start_index=text.find(entry_text[:50]),
                    end_index=text.find(entry_text[:50]) + len(entry_text),
                    metadata={"lemma": lemma}
                ))
        
        return chunks if chunks else self._chunk_dogmatics(text, max_size)
    
    def _chunk_commentary(self, text: str, max_size: int) -> List[SemanticChunk]:
        """주석: 성경 절 단위 분할"""
        chunks = []
        
        # 성경 참조 패턴 (예: "1:1", "v. 1", "verse 1")
        verse_pattern = re.compile(
            r'(?:^|\n)(?:(?:\d+:)?\d+\.?\s+|v\.?\s*\d+|verse\s+\d+)',
            re.IGNORECASE | re.MULTILINE
        )
        
        parts = verse_pattern.split(text)
        refs = verse_pattern.findall(text)
        
        for i, part in enumerate(parts):
            if len(part.strip()) < 30:
                continue
            
            ref = refs[i-1].strip() if i > 0 and i <= len(refs) else ""
            
            # 긴 부분은 문단으로 추가 분할
            if len(part) > max_size * 4:
                sub_chunks = self._split_by_paragraph(part, max_size)
                for j, sub in enumerate(sub_chunks):
                    chunks.append(SemanticChunk(
                        content=sub,
                        chunk_type="verse",
                        start_index=text.find(sub[:50]) if len(sub) > 50 else 0,
                        end_index=0,
                        metadata={"verse_ref": ref, "sub_index": j}
                    ))
            else:
                chunks.append(SemanticChunk(
                    content=part.strip(),
                    chunk_type="verse",
                    start_index=text.find(part[:50]) if len(part) > 50 else 0,
                    end_index=0,
                    metadata={"verse_ref": ref}
                ))
        
        return chunks if chunks else self._chunk_dogmatics(text, max_size)
    
    def _chunk_dogmatics(self, text: str, max_size: int) -> List[SemanticChunk]:
        """교의학: 논증/문단 단위 분할"""
        chunks = []
        
        # 1. 먼저 헤딩으로 분할 시도
        sections = self._split_by_heading(text)
        
        for section_text, heading in sections:
            # 각 섹션을 문단으로 분할
            paragraphs = self._split_by_paragraph(section_text, max_size)
            
            for j, para in enumerate(paragraphs):
                if len(para.strip()) < 50:
                    continue
                
                chunks.append(SemanticChunk(
                    content=para,
                    chunk_type="paragraph" if not heading else "section",
                    start_index=text.find(para[:50]) if len(para) > 50 else 0,
                    end_index=0,
                    metadata={"section_heading": heading, "para_index": j}
                ))
        
        return chunks
    
    def _split_by_lemma(self, text: str) -> List[tuple]:
        """표제어 단위로 분할"""
        entries = []
        
        # 간단한 휴리스틱: 그리스/히브리어로 시작하는 줄
        lines = text.split('\n')
        current_entry = []
        current_lemma = ""
        
        for line in lines:
            # 새 표제어 시작?
            match = self.LEMMA_PATTERN.match(line)
            if match:
                # 이전 항목 저장
                if current_entry:
                    entries.append(('\n'.join(current_entry), current_lemma))
                current_entry = [line]
                current_lemma = match.group(1)
            else:
                current_entry.append(line)
        
        # 마지막 항목
        if current_entry:
            entries.append(('\n'.join(current_entry), current_lemma))
        
        return entries if entries else [(text, "")]
    
    def _split_by_heading(self, text: str) -> List[tuple]:
        """헤딩 단위로 분할"""
        sections = []
        
        matches = list(self.HEADING_PATTERN.finditer(text))
        
        if not matches:
            return [(text, "")]
        
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            heading = match.group(1).strip()
            section_text = text[start:end].strip()
            
            if section_text:
                sections.append((section_text, heading))
        
        # 첫 헤딩 이전 내용
        if matches and matches[0].start() > 0:
            pre_text = text[:matches[0].start()].strip()
            if pre_text:
                sections.insert(0, (pre_text, ""))
        
        return sections if sections else [(text, "")]
    
    def _split_by_paragraph(self, text: str, max_size: int) -> List[str]:
        """문단 단위로 분할 (크기 제한 적용)"""
        # 문단 분리
        paragraphs = re.split(r'\n\s*\n', text)
        
        result = []
        current = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 현재 + 새 문단이 제한을 초과?
            if len(current) + len(para) > max_size * 4:  # 대략적 토큰 추정
                if current:
                    result.append(current)
                current = para
            else:
                current = current + "\n\n" + para if current else para
        
        if current:
            result.append(current)
        
        return result


# ============================================================
# Convenience Function
# ============================================================
def semantic_chunk(text: str, 
                   doc_type: str = "dogmatics",
                   max_size: int = 1200) -> List[Dict[str, Any]]:
    """
    시맨틱 청킹 편의 함수.
    
    Args:
        text: 원본 텍스트
        doc_type: 문서 유형
        max_size: 최대 청크 크기
        
    Returns:
        청크 딕셔너리 리스트
    """
    chunker = SemanticChunker()
    chunks = chunker.chunk(text, doc_type, max_size)
    
    return [
        {
            "content": c.content,
            "chunk_type": c.chunk_type,
            "start_index": c.start_index,
            "metadata": c.metadata
        }
        for c in chunks
    ]


if __name__ == "__main__":
    # 테스트
    test_dict = """
ἀγάπη (agapē) - love, divine love
    1. Etymology and Usage
    The term ἀγάπη appears throughout the NT...
    
    2. Theological Significance
    In contrast to eros and philia...

λόγος (logos) - word, reason
    1. Background
    The concept of logos has philosophical roots...
    """
    
    test_dogma = """
# Chapter 1: The Doctrine of God

## 1.1 The Being of God

God's being is not a static substance but a living act...

## 1.2 The Trinity

The doctrine of the Trinity affirms that God is one essence...
    """
    
    chunker = SemanticChunker()
    
    print("="*60)
    print("📚 Dictionary Test")
    print("="*60)
    for c in chunker.chunk(test_dict, "dictionary", 500):
        print(f"\n[{c.chunk_type}] {c.metadata}")
        print(c.content[:100] + "...")
    
    print("\n" + "="*60)
    print("📖 Dogmatics Test")
    print("="*60)
    for c in chunker.chunk(test_dogma, "dogmatics", 500):
        print(f"\n[{c.chunk_type}] {c.metadata}")
        print(c.content[:100] + "...")
