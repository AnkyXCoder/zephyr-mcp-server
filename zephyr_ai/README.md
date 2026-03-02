# Zephyr AI Platform

Production-grade Embedded AI MCP Platform for Zephyr RTOS.

Features:
- West build/flash/twister
- Kconfig intelligence
- Devicetree analysis
- Log & fault parsing
- MCUboot image analysis
- West manifest reasoning
- Static analysis (cppcheck)

---

## Install (5 Minutes)

1. Clone project
2. cd zephyr-ai-platform
3. python -m venv venv
4. source venv/bin/activate
5. pip install -r requirements.txt
6. python run_server.py

---

## Claude Desktop Integration

Add to config:

```json
{
  "mcpServers": {
    "zephyr-ai-platform": {
      "args": [
        "<path_to_zephyr_mcp>/run_server.py"
      ],
      "command": "<path_to_virtual_env>/.venv/bin/python",
      "disabled": false,
      "env": {
        "ZEPHYR_BASE": "<path_to_zephyr>/"
      }
    }
  }
}
```

Restart Claude Desktop.

---

## Example Prompts

- Build my app for nrf52840dk_nrf52840
- Search Kconfig symbol CONFIG_BT
- Analyze my west.yml
- Run cppcheck on modules
- Analyze MCUboot image

---

This platform is modular and extensible.
Add new tools under zephyr_ai/ and register them in server.py
