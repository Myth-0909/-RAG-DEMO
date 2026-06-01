---
name: python313-rag-stack-compat
description: Python 3.13 环境下 RAG 技术栈（bcrypt/passlib/pymilvus/setuptools）的兼容性问题和修复方案
source: auto-skill
extracted_at: '2026-06-01T01:34:34.803Z'
---

# Python 3.13 RAG 技术栈兼容性问题

在 Python 3.13 环境下搭建 FastAPI + Milvus + LangChain RAG 项目时，会遇到多个依赖兼容性问题。

## 问题 1: passlib 与 bcrypt >= 4.1 不兼容

**现象**: `AttributeError: module 'bcrypt' has no attribute '__about__'`，以及 `ValueError: password cannot be longer than 72 bytes`

**原因**: passlib 1.7.4 内部通过 `_bcrypt.__about__.__version__` 检测 bcrypt 版本，但 bcrypt 4.1+ 已移除该属性。passlib 项目长期未更新，无法适配新版 bcrypt。

**修复方案**: 弃用 passlib，直接使用 bcrypt 库：

```python
import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
```

requirements.txt 中移除 `passlib[bcrypt]`，只保留 `bcrypt`。

## 问题 2: setuptools >= 82 移除 pkg_resources

**现象**: `ModuleNotFoundError: No module named 'pkg_resources'`（pymilvus 依赖它）

**原因**: setuptools 82.0+ 正式移除了已废弃的 `pkg_resources` 模块，而 pymilvus 等库仍在 `__init__.py` 中使用 `from pkg_resources import DistributionNotFound, get_distribution`。

**修复方案**: 在 requirements.txt 中锁定 setuptools 版本：

```
setuptools<81
```

注意：`pip install setuptools` 默认会安装最新版（>= 82），即使 `--force-reinstall` 也无法解决，必须显式指定版本约束。

## 问题 3: create-vite 等交互式 CLI 在非交互环境中超时

**现象**: `npx create-vite` 或 `npm create vite@latest` 等待用户输入框架选择，导致超时。

**修复方案**: 手动搭建项目结构，直接创建 `package.json`、`vite.config.ts`、`tsconfig.json`、`index.html` 等文件，然后 `npm install`。避免依赖交互式 CLI。

## 可用的 requirements.txt 模板（Python 3.13 + RAG）

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.18
sqlalchemy==2.0.36
alembic==1.14.0
python-jose[cryptography]==3.3.0
bcrypt
pydantic==2.10.3
pydantic-settings==2.7.0
pymilvus==2.4.9
openai==1.58.1
langchain==0.3.13
langchain-community==0.3.13
langchain-openai==0.2.14
langchain-text-splitters==0.3.4
pypdf==5.1.0
python-docx==1.1.2
sse-starlette==2.2.1
python-dotenv==1.0.1
httpx==0.28.1
setuptools<81
```
