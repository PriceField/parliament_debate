# 宣告偽目標（這些名稱不對應實際檔案，每次執行都強制跑）
.PHONY: install setup run list-sessions test clean

# 虛擬環境內的 Python / pip 路徑（Windows .venv 結構）
PYTHON := .venv/Scripts/python
PIP    := .venv/Scripts/pip

# 建立虛擬環境（若不存在）並安裝所有依賴
install:
	@test -d .venv || python -m venv .venv
	$(PIP) install -r requirements.txt

# 從範本產生 .env（若已存在則跳過，避免覆蓋已填好的 key）
setup:
	@test -f .env || (cp .env.example .env && echo "Created .env — fill in ANTHROPIC_API_KEY (required) and any optional keys")

# 顯示 debate.py 的使用說明（不實際執行辯論）
run:
	@echo "Usage: $(PYTHON) debate.py --topic \"your topic here\" [--rounds N] [--seed N] [--context TEXT] [--output FILE]"
	@echo "       $(PYTHON) debate.py --resume <session_id>"
	@echo "       $(PYTHON) debate.py --list-sessions"

# 列出所有已儲存的辯論 session（可用 --resume 繼續）
list-sessions:
	$(PYTHON) debate.py --list-sessions

# 對每個已配置的 model 送出 ping，確認 API key 與 endpoint 正常
test:
	$(PYTHON) test_models.py

# 清除快取與 SQLite checkpoint 資料庫
clean:
	rm -rf __pycache__
	rm -f *.db
	@echo "Cleaned."
