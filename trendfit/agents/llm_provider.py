"""Provedores LLM abstratos com HTTP (sem SDKs pesados).

Cascade adaptativo: tenta Gemini → Moonshot/Kimi → Groq na ordem.
Pula provider se API key ausente no .env. Failover automático em erro/quota.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Interface abstrata para provedor LLM."""

    @abstractmethod
    def complete(self, system: str, messages: list[dict]) -> str:
        """Gera resposta usando system prompt e histórico de mensagens.

        Args:
            system: System prompt (personagem/contexto)
            messages: Lista de {role: "user"|"assistant", content: str}

        Returns:
            Texto da resposta do LLM

        Raises:
            RuntimeError: Se falhar (quota, timeout, etc)
        """


class GeminiProvider(LLMProvider):
    """Google Gemini via HTTP REST (sem SDK)."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    def complete(self, system: str, messages: list[dict]) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini: API_KEY não configurada (GEMINI_API_KEY)")

        # Converte histórico para formato Gemini: contents = [{"role", "parts"}]
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "model", "parts": [{"text": "Entendido. Vou agir conforme descrito."}]})

        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2000,
                "topP": 0.95,
            }
        }

        try:
            url = f"{self._base_url}?key={self.api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            candidates = result.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            raise RuntimeError("Gemini: resposta vazia")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RuntimeError("Gemini: quota excedida (429)") from e
            raise RuntimeError(f"Gemini HTTP erro {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Gemini: erro de rede {e.reason}") from e


class MoonShotProvider(LLMProvider):
    """Moonshot/Kimi via HTTP REST (sem SDK)."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("MOONSHOT_API_KEY", "")
        self._base_url = "https://api.moonshot.cn/v1/chat/completions"

    def complete(self, system: str, messages: list[dict]) -> str:
        if not self.api_key:
            raise RuntimeError("Moonshot: API_KEY não configurada (MOONSHOT_API_KEY)")

        # Monta mensagens com system prompt
        api_messages = [{"role": "system", "content": system}] if system else []
        api_messages.extend(messages)

        payload = {
            "model": "moonshot-v1-8k",
            "messages": api_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        try:
            req = urllib.request.Request(
                self._base_url,
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            raise RuntimeError("Moonshot: resposta vazia")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RuntimeError("Moonshot: quota excedida (429)") from e
            raise RuntimeError(f"Moonshot HTTP erro {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Moonshot: erro de rede {e.reason}") from e


class GroqProvider(LLMProvider):
    """Groq API via HTTP REST (sem SDK)."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._base_url = "https://api.groq.com/openai/v1/chat/completions"

    def complete(self, system: str, messages: list[dict]) -> str:
        if not self.api_key:
            raise RuntimeError("Groq: API_KEY não configurada (GROQ_API_KEY)")

        # Monta mensagens com system prompt
        api_messages = [{"role": "system", "content": system}] if system else []
        api_messages.extend(messages)

        payload = {
            "model": "llama-3.3-70b-versatile",  # mixtral-8x7b foi aposentado pela Groq
            "messages": api_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        try:
            req = urllib.request.Request(
                self._base_url,
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            raise RuntimeError("Groq: resposta vazia")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RuntimeError("Groq: quota excedida (429)") from e
            raise RuntimeError(f"Groq HTTP erro {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Groq: erro de rede {e.reason}") from e


class GeminiCliProvider(LLMProvider):
    """Gemini via CLI local (`gemini`), logado por OAuth — custo zero, sem API key.

    Stateless por invocação: serializa system + histórico num prompt único no stdin.
    Mitigação de segurança (o CLI traz tools de filesystem ligadas por padrão):
    roda em diretório temporário VAZIO + --approval-mode plan (read-only).

    Busca web: o modo `plan` (read-only) permite a tool de busca do CLI sem prompt
    interativo — então o agente PODE pesquisar dados/notícias atualizados, sem
    reabrir acesso de escrita ao filesystem. Daí o timeout maior (busca + retries).
    """

    def __init__(self, model: str | None = None, timeout: int = 150):
        self.model = model
        self.timeout = timeout

    def complete(self, system: str, messages: list[dict]) -> str:
        if shutil.which("gemini") is None:
            raise RuntimeError("Gemini CLI não encontrado (instale e faça login)")

        # Serializa tudo num prompt único (o CLI é single-turn)
        parts = []
        if system:
            parts.append(f"System: {system}")
        if messages:
            parts.append("Histórico da conversa:")
            for msg in messages:
                parts.append(f"{msg['role']}: {msg['content']}")
        parts.append("Responda à última mensagem do usuário em português.")
        prompt = "\n\n".join(parts)

        cmd = ["gemini", "-p", "", "-o", "text", "--approval-mode", "plan"]
        if self.model:
            cmd.extend(["-m", self.model])

        # cwd = diretório temporário vazio: nada sensível pro CLI ler/vazar
        tmpdir = tempfile.mkdtemp()
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Gemini CLI: timeout") from e
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        if result.returncode != 0:
            raise RuntimeError(f"Gemini CLI erro: {result.stderr[:200]}")
        output = result.stdout.strip()
        if not output:
            raise RuntimeError("Gemini CLI: resposta vazia")
        return output


class CascadeProvider(LLMProvider):
    """Tenta múltiplos provedores na ordem até sucesso."""

    def __init__(self, providers: list[LLMProvider] | None = None):
        if providers is None:
            # Padrão: Gemini CLI (OAuth, custo zero) → Gemini/Moonshot/Groq (API key)
            providers = [
                GeminiCliProvider(),
                GeminiProvider(),
                MoonShotProvider(),
                GroqProvider(),
            ]
        self.providers = [p for p in providers if self._is_available(p)]
        if not self.providers:
            raise RuntimeError("Nenhum provedor LLM disponível (faltam API keys em .env)")

    @staticmethod
    def _is_available(provider: LLMProvider) -> bool:
        """Verifica se provider tem API key configurada (ou CLI disponível)."""
        if isinstance(provider, GeminiCliProvider):
            return shutil.which("gemini") is not None
        if isinstance(provider, GeminiProvider):
            return bool(os.environ.get("GEMINI_API_KEY", ""))
        if isinstance(provider, MoonShotProvider):
            return bool(os.environ.get("MOONSHOT_API_KEY", ""))
        if isinstance(provider, GroqProvider):
            return bool(os.environ.get("GROQ_API_KEY", ""))
        return True  # Providers customizados assumidos disponíveis

    def complete(self, system: str, messages: list[dict]) -> str:
        """Tenta cada provedor até sucesso."""
        errors = []
        for provider in self.providers:
            try:
                return provider.complete(system, messages)
            except RuntimeError as e:
                logger.debug("Failover de %s: %s", provider.__class__.__name__, str(e))
                errors.append((provider.__class__.__name__, str(e)))
        raise RuntimeError(f"Todos os provedores falharam: {errors}")
