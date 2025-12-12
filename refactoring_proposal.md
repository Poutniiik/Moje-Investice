# Refactoring Proposal: Investment Terminal Application

This document outlines a proposal for refactoring the current monolithic Streamlit application into a modular, maintainable, and scalable architecture.

## 1. Code Structure Analysis

### 1.1. Monolithic Files and SRP Violations

*   **`web_investice.py` (Critical)**
    *   **Size:** ~1600 lines.
    *   **Responsibilities:**
        *   **UI Rendering:** Handles layout and rendering for all pages (Dashboard, Watchlist, Analysis, News, Trading, Dividends, Gamification, Settings, Bank).
        *   **Application Logic:** Contains the main execution loop, authentication logic, and state management.
        *   **Business Logic:** Performs calculations for portfolio performance, buy/sell operations, currency conversion, and data orchestration.
        *   **Data Fetching:** Orchestrates calls to `utils.py` and `data_manager.py` and manages caching (`st.cache_data`).
        *   **Styling:** Injects CSS directly into the page.
    *   **SRP Violation:** This file effectively does "everything". It is difficult to read, test, and maintain. A change in the UI risks breaking business logic and vice-versa.

*   **`utils.py` (Moderate)**
    *   **Size:** ~13KB.
    *   **Responsibilities:** Mixed bag of utility functions.
        *   **Data Fetching:** `ziskej_info`, `ziskej_yield`, `ziskej_ceny_hromadne`.
        *   **Reporting:** `vytvor_pdf_report`.
        *   **Plotting:** `make_plotly_cyberpunk`.
        *   **External APIs:** Fear & Greed index, RSS parsing.
    *   **SRP Violation:** It acts as a "junk drawer" for any helper function. Plotting logic should be separate from data fetching logic.

### 1.2. Other Files
*   `data_manager.py`: Handles CSV persistence to GitHub. Relatively focused but mixes GitHub logic with general data interface.
*   `bank_engine.py`: Focused on banking simulation/integration. Good.
*   `ai_brain.py`: Focused on AI interactions. Good, though `web_investice.py` still contains some AI initialization logic.
*   `notification_engine.py`: Focused on Telegram notifications. Good.
*   `styles.py`: Focused on CSS. Good.

## 2. Dependencies

### 2.1. Current Dependency Graph
*   `web_investice.py` depends on: `notification_engine`, `bank_engine`, `utils`, `styles`, `data_manager`, `ai_brain` + many external libs (`streamlit`, `pandas`, `yfinance`, `plotly`, etc.).
*   `utils.py` depends on: `data_manager` (for constants), `yfinance`, `pandas`, `requests`, `fpdf`, `plotly`, `matplotlib`.
*   `ai_brain.py` depends on: `google.generativeai`.

### 2.2. Issues
*   **Centralized Coupling:** `web_investice.py` is coupled to everything. Refactoring any subsystem requires checking this main file.
*   **Mixed Abstractions:** UI code in `web_investice.py` directly calls low-level data saving functions in `data_manager.py` and calculation logic.

## 3. Proposed Refactoring Plan

The goal is to move towards a modular architecture separating **UI**, **Business Logic (Services)**, and **Data Access**.

### 3.1. Directory Structure

```text
src/
├── app.py                  # Main entry point (replaces web_investice.py)
├── config.py               # Central configuration (constants)
├── ui/                     # UI Components and Pages
│   ├── __init__.py
│   ├── styles.py           # Existing styles.py
│   ├── layout.py           # Common layout functions (sidebar, header)
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── dashboard.py    # render_prehled_page
│   │   ├── watchlist.py    # render_sledovani_page
│   │   ├── analysis.py     # render_analýza_* functions
│   │   ├── news.py         # News page
│   │   ├── trading.py      # render_obchod_page
│   │   ├── dividends.py    # render_dividendy_page
│   │   ├── gamification.py # render_gamifikace_page
│   │   ├── settings.py     # render_nastaveni_page
│   │   └── bank.py         # render_bank_lab_page
│   └── components/         # Reusable UI widgets
│       ├── __init__.py
│       ├── charts.py       # Plotting functions from utils.py
│       └── widgets.py      # e.g., ticker tape, metric cards
├── services/               # Business Logic
│   ├── __init__.py
│   ├── portfolio_service.py # Calculations, buy/sell logic
│   ├── market_data.py      # Fetching prices, details (from utils.py)
│   ├── ai_service.py       # Wrapper around ai_brain.py
│   ├── reporting.py        # PDF generation
│   └── notification.py     # Wrapper around notification_engine.py
├── data/                   # Data Access Layer
│   ├── __init__.py
│   ├── storage.py          # Abstracted data storage (CSV/GitHub)
│   └── bank_integration.py # Wrapper around bank_engine.py
└── utils/                  # True utilities
    ├── __init__.py
    └── helpers.py          # Generic helpers (formatting, etc.)
```

### 3.2. Step-by-Step Refactoring

1.  **Extract Configuration:**
    *   Move constants (`REPO_NAZEV`, file names, `RISK_FREE_RATE`) from `data_manager.py` and `web_investice.py` to `src/config.py`.

2.  **Modularize `utils.py`:**
    *   Move plotting functions (`make_plotly_cyberpunk`, `make_matplotlib_cyberpunk`) to `src/ui/components/charts.py`.
    *   Move PDF generation to `src/services/reporting.py`.
    *   Move data fetching functions (`ziskej_info`, `ziskej_yield`, etc.) to `src/services/market_data.py`.

3.  **Service Layer Extraction:**
    *   Create `src/services/portfolio_service.py`. Move logic for `proved_nakup`, `proved_prodej`, `calculate_all_data`, and `calculate_sharpe_ratio` here.
    *   Ensure these functions return data/objects, not UI elements.

4.  **UI Page Extraction:**
    *   Create separate modules in `src/ui/pages/` for each major page currently in `web_investice.py`.
    *   Example: Move `render_prehled_page` to `src/ui/pages/dashboard.py`.
    *   Pass necessary data (DataFrames, services) as arguments to these render functions, or use a dependency injection pattern / Singleton state manager.

5.  **Main Application Entry Point (`src/app.py`):**
    *   Rewrite `web_investice.py` as `src/app.py`.
    *   It should handle:
        *   Streamlit configuration (`set_page_config`).
        *   Authentication (Login/Register).
        *   Initialization of services and session state.
        *   Main navigation routing (calling render functions from `src/ui/pages/`).

### 3.3. Benefits
*   **Maintainability:** Smaller, focused files are easier to understand and edit.
*   **Testability:** Business logic in `services/` can be tested independently of the Streamlit UI.
*   **Reusability:** UI components and service functions can be reused across different pages.
*   **Scalability:** Easier to add new pages or features without cluttering the main file.
