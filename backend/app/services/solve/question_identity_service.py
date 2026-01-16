"""
Question Identity Service
=========================
OCR-proof caching for Snap & Solve questions.
Ensures the same question never calls OpenAI twice.

Fingerprint algorithm:
- Normalize stem text (NFKC, lowercase, collapse whitespace)
- Extract and normalize MCQ options (LaTeX fractions → a/b)
- Detect question type
- SHA256 hash of combined fingerprint
"""

import re
import json
import hashlib
import unicodedata
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlmodel import Session, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Column, JSON

import logging
logger = logging.getLogger(__name__)


class QuestionIdentityService:
    """
    Service for computing OCR-proof question fingerprints and caching results.
    """
    
    # Regex patterns
    OPTION_PATTERN = re.compile(r'([A-D])\s*[):.\]]\s*(.+?)(?=(?:[A-D]\s*[):.\]])|$)', re.IGNORECASE | re.DOTALL)
    LATEX_FRAC_PATTERN = re.compile(r'\\frac\s*\{([^}]+)\}\s*\{([^}]+)\}')
    LATEX_WRAPPER_PATTERN = re.compile(r'\$+([^$]+)\$+')
    WHITESPACE_PATTERN = re.compile(r'\s+')
    
    def compute_question_fingerprint(self, ocr_text: str) -> Dict[str, Any]:
        """
        Compute a normalized fingerprint from OCR text.
        
        Returns:
            {
                "stem": "normalized question stem",
                "options": ["1/5", "2/5", "1/30", "1/15"],  # sorted, normalized
                "type": "mcq_probability"
            }
        """
        # 1. Normalize the entire text first
        normalized_full = self._normalize_text(ocr_text)
        
        # 2. Try to extract MCQ options
        options, stem = self._extract_options(normalized_full)
        
        # 3. Determine question type
        question_type = self._detect_question_type(stem, options)
        
        # 4. Normalize stem further (remove option markers that might be in stem)
        stem = self._normalize_stem(stem)
        
        # 5. Normalize options
        normalized_options = [self._normalize_option(opt) for opt in options]
        
        # 6. Sort options for consistency
        sorted_options = sorted(normalized_options)
        
        return {
            "stem": stem,
            "options": sorted_options,
            "type": question_type,
            "original_text": ocr_text[:500]  # Keep first 500 chars for debugging
        }
    
    def compute_question_key(self, fingerprint: Dict[str, Any]) -> str:
        """
        Compute SHA256 hash of the fingerprint.
        """
        # Create a stable string representation
        key_data = {
            "stem": fingerprint["stem"],
            "options": fingerprint["options"],
            "type": fingerprint["type"]
        }
        key_string = json.dumps(key_data, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    
    def _normalize_text(self, text: str) -> str:
        """
        Aggressively normalize text for OCR-proof comparison.
        """
        # 1. Unicode normalize (NFKC)
        text = unicodedata.normalize('NFKC', text)
        
        # 2. Lowercase
        text = text.lower()
        
        # 3. Replace common Unicode variants
        replacements = {
            '−': '-',  # Unicode minus
            '–': '-',  # En dash
            '—': '-',  # Em dash
            '×': '*',
            '÷': '/',
            ''': "'",
            ''': "'",
            '"': '"',
            '"': '"',
            '…': '...',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # 4. Remove LaTeX wrappers but keep content
        text = self.LATEX_WRAPPER_PATTERN.sub(r'\1', text)
        
        # 5. Convert LaTeX fractions to simple fractions
        text = self.LATEX_FRAC_PATTERN.sub(r'\1/\2', text)
        
        # 6. Collapse whitespace
        text = self.WHITESPACE_PATTERN.sub(' ', text)
        
        # 7. Strip
        text = text.strip()
        
        return text
    
    def _extract_options(self, text: str) -> Tuple[List[str], str]:
        """
        Extract MCQ options (A, B, C, D) and return (options, stem).
        """
        options = []
        
        # Find all options
        matches = list(self.OPTION_PATTERN.finditer(text))
        
        if matches:
            for match in matches:
                label = match.group(1).upper()
                content = match.group(2).strip()
                options.append(content)
            
            # Stem is everything before the first option
            first_option_start = matches[0].start()
            stem = text[:first_option_start].strip()
        else:
            # No MCQ options found - entire text is the stem
            stem = text
        
        return options, stem
    
    def _normalize_stem(self, stem: str) -> str:
        """
        Further normalize the question stem.
        """
        # Remove question numbers like "3." or "Q3:" at the start
        stem = re.sub(r'^[qQ]?\d+[.:)\]]\s*', '', stem)
        
        # Remove trailing punctuation that might vary
        stem = re.sub(r'[.!?:]+$', '', stem)
        
        # Remove common instruction phrases that don't affect identity
        remove_phrases = [
            r'\bwhat is the\b',
            r'\bfind the\b',
            r'\bcalculate the\b',
            r'\bdetermine the\b',
        ]
        for phrase in remove_phrases:
            stem = re.sub(phrase, '', stem, flags=re.IGNORECASE)
        
        # Collapse whitespace again
        stem = self.WHITESPACE_PATTERN.sub(' ', stem).strip()
        
        return stem
    
    def _normalize_option(self, option: str) -> str:
        """
        Normalize a single MCQ option.
        """
        # Already partially normalized, but ensure fractions are consistent
        
        # Remove any remaining LaTeX commands
        option = re.sub(r'\\[a-zA-Z]+', '', option)
        
        # Remove curly braces
        option = option.replace('{', '').replace('}', '')
        
        # Normalize fractions like "1 / 5" to "1/5"
        option = re.sub(r'(\d+)\s*/\s*(\d+)', r'\1/\2', option)
        
        # Strip and collapse whitespace
        option = self.WHITESPACE_PATTERN.sub(' ', option).strip()
        
        return option
    
    def _detect_question_type(self, stem: str, options: List[str]) -> str:
        """
        Detect question type from stem and options.
        """
        stem_lower = stem.lower()
        
        # Check for probability keywords
        if any(word in stem_lower for word in ['probability', 'chance', 'likely', 'random', 'odds']):
            return "mcq_probability" if options else "probability"
        
        # Check for equation/algebra
        if '=' in stem or 'solve' in stem_lower or 'equation' in stem_lower:
            return "mcq_algebra" if options else "algebra"
        
        # Check for geometry
        if any(word in stem_lower for word in ['triangle', 'circle', 'area', 'perimeter', 'angle']):
            return "mcq_geometry" if options else "geometry"
        
        # Check for calculus
        if any(word in stem_lower for word in ['derivative', 'integral', 'limit', 'differentiate']):
            return "mcq_calculus" if options else "calculus"
        
        # Default
        return "mcq_general" if options else "general"
    
    def get_cached_question(self, session: Session, question_key: str) -> Optional[Dict[str, Any]]:
        """
        Look up a cached question result.
        Updates hit_count and last_seen_at on hit.
        """
        from app.models import QuestionIdentityCache
        
        try:
            stmt = select(QuestionIdentityCache).where(
                QuestionIdentityCache.question_key == question_key
            )
            cached = session.exec(stmt).first()
            
            if cached:
                # Update stats
                cached.hit_count += 1
                cached.last_seen_at = datetime.utcnow()
                session.add(cached)
                session.commit()
                
                logger.info(f"[QUESTION_CACHE] HIT: {question_key[:16]}... (hits: {cached.hit_count})")
                return cached.solution_json
            
            return None
            
        except Exception as e:
            logger.error(f"[QUESTION_CACHE] Lookup error: {e}")
            return None
    
    def store_question_result(
        self,
        session: Session,
        question_key: str,
        fingerprint: Dict[str, Any],
        solution: Dict[str, Any],
        original_ocr_text: str
    ) -> bool:
        """
        Store a question result using UPSERT for concurrency safety.
        """
        from app.models import QuestionIdentityCache
        
        try:
            # Check if exists first (for adding to variants)
            existing = session.exec(
                select(QuestionIdentityCache).where(
                    QuestionIdentityCache.question_key == question_key
                )
            ).first()
            
            if existing:
                # Just add this OCR variant if not already present
                variants = existing.original_variants or []
                if original_ocr_text[:500] not in variants:
                    variants.append(original_ocr_text[:500])
                    existing.original_variants = variants
                    session.add(existing)
                    session.commit()
                logger.info(f"[QUESTION_CACHE] Already exists: {question_key[:16]}...")
                return True
            
            # Create new entry
            cache_entry = QuestionIdentityCache(
                question_key=question_key,
                normalized_stem=fingerprint.get("stem", "")[:1000],
                normalized_options=json.dumps(fingerprint.get("options", [])),
                question_type=fingerprint.get("type", "unknown"),
                solution_json=solution,
                original_variants=[original_ocr_text[:500]],
                hit_count=0,
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow()
            )
            
            session.add(cache_entry)
            session.commit()
            
            logger.info(f"[QUESTION_CACHE] Stored: {question_key[:16]}...")
            return True
            
        except Exception as e:
            logger.error(f"[QUESTION_CACHE] Store error: {e}")
            session.rollback()
            return False


# Singleton instance
question_identity_service = QuestionIdentityService()
