# Charts component
import plotly.graph_objects as go
import matplotlib.pyplot as plt

# --- 1. STYLOVÁNÍ PRO PLOTLY (Interaktivní) ---
def make_plotly_cyberpunk(fig):
    """Aplikuje Cyberpunk skin na Plotly graf bezpečně podle typu trace."""
    neon_green = "#00FF99"
    dark_bg = "rgba(0,0,0,0)"
    grid_color = "#30363D"

    # Layout styling (bezpečné, univerzální)
    try:
        fig.update_layout(
            paper_bgcolor=dark_bg,
            plot_bgcolor=dark_bg,
            font=dict(color=neon_green, family="Courier New"),
            xaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color, showline=True, linecolor=grid_color),
            yaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color, showline=True, linecolor=grid_color),
            legend=dict(bgcolor=dark_bg, bordercolor=grid_color, borderwidth=1),
            hovermode="x unified"
        )
    except Exception:
        pass

    # Aplikuj styl selektivně podle typu trace
    try:
        for t in fig.data:
            t_type = getattr(t, "type", None)

            # PIE: obrys se nastavuje přes marker.line
            if t_type == "pie":
                try:
                    current_marker = dict(t.marker) if getattr(t, "marker", None) is not None else {}
                    current_marker["line"] = dict(width=3, color=neon_green)
                    t.marker = current_marker
                except Exception:
                    try:
                        t.marker = {"line": dict(width=3, color=neon_green)}
                    except Exception:
                        pass

            # Trace, které běžně podporují line
            elif t_type in ("scatter", "bar", "line", "ohlc", "candlestick"):
                try:
                    t.line = dict(width=3, color=neon_green)
                except Exception:
                    pass

            # Fallback: pokud má trace marker, pokusíme se nastavit marker.line
            else:
                try:
                    if hasattr(t, "marker"):
                        m = dict(t.marker) if getattr(t, "marker", None) is not None else {}
                        m["line"] = dict(width=3, color=neon_green)
                        t.marker = m
                except Exception:
                    pass
    except Exception:
        pass

    return fig

# --- 2. STYLOVÁNÍ PRO MATPLOTLIB (Statické) ---
def make_matplotlib_cyberpunk(fig, ax):
    """Aplikuje Cyberpunk skin na Matplotlib Figure a Axes."""
    neon_green = "#00FF99"
    dark_bg = "#0E1117"
    text_color = "#00FF99"
    grid_color = "#30363D"

    fig.patch.set_facecolor(dark_bg)
    ax.set_facecolor(dark_bg)

    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)
    ax.title.set_color(text_color)

    ax.tick_params(axis='x', colors=text_color)
    ax.tick_params(axis='y', colors=text_color)

    for spine in ax.spines.values():
        spine.set_edgecolor(grid_color)

    ax.grid(True, color=grid_color, linestyle='--', linewidth=0.5, alpha=0.5)

    return fig
