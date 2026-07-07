"""MySpresso event-button chip styles.

The template is generated per-theme from the design tokens (call
:func:`artisan_event_button_style` at apply time — main.py formats the
result with the size placeholders). States follow upstream Artisan
semantics: ``Selected`` = the event the roast is currently in (accent
red), ``flat`` = already fired / replayed (quiet sunken chip).
"""

from artisanlib.styles import current_semantic_tokens
from artisanlib.util import createGradient


def artisan_event_button_style() -> str:
    """Theme-resolved QSS template for the event-button row.

    Keeps the historical ``.format()`` placeholders: min_width,
    min_height, padding, default_font_size, selected_font_size.
    """
    tok = current_semantic_tokens()
    accent_grad = createGradient(tok.accent)
    accent_pressed = createGradient(tok.error_fg if not tok.dark else tok.accent)
    return (
        """
            EventPushButton {{
                min-width: {min_width}px;
                min-height: {min_height}px;
                font-size: {default_font_size}pt;
                font-weight: bold;
                padding: {padding}px;
                border-style:solid;
                border-radius:4;
                border-color:grey;
                border-width:0;
                color: """ + tok.fg_on_brand + """;
            }}
            EventPushButton:!enabled {{
                color: """ + tok.fg_muted + """;
                background-color: """ + tok.surface_alt + """;
            }}

            EventPushButton[Selected=true] {{
                font-size: {selected_font_size}pt;
                background-color:""" + accent_grad + """ ;
            }}
            EventPushButton[Selected=true]:flat {{
                color: """ + tok.fg_muted + """;
                background-color: """ + tok.surface_alt + """;
            }}
            EventPushButton[Selected=true]:flat:!pressed:hover {{
                color: """ + tok.fg_on_brand + """;
                background-color: """ + accent_grad + """;
            }}
            EventPushButton[Selected=true]:flat:pressed {{
                color: """ + tok.fg_on_brand + """;
                background-color: """ + tok.accent + """;
            }}
            EventPushButton[Selected=true]:!flat:pressed {{
                color: """ + tok.fg_on_brand + """;
                background-color:""" + accent_pressed + """ ;
            }}
            EventPushButton[Selected=true]:!pressed:hover {{
                color: """ + tok.fg_on_brand + """;
                background-color:""" + accent_grad + """ ;
            }}

            MajorEventPushButton[Selected=false]:flat {{
                color: """ + tok.fg_muted + """;
                background-color: """ + tok.surface_alt + """;
            }}
            MajorEventPushButton[Selected=false]:flat:!pressed:hover {{
                color: """ + tok.fg_secondary + """;
                background-color: """ + tok.border + """;
            }}
            MajorEventPushButton[Selected=false]:flat:pressed {{
                color: """ + tok.fg_secondary + """;
                background-color: """ + tok.border_strong + """;
            }}
            MajorEventPushButton[Selected=false]:!flat:pressed {{
                color: """ + tok.fg_on_brand + """;
                background-color:""" + createGradient(tok.brand) + """ ;
            }}
            MajorEventPushButton[Selected=false]:!pressed:hover {{
                background-color:""" + createGradient(tok.brand) + """ ;
            }}

            MinorEventPushButton[Selected=false]:flat {{
                color: """ + tok.fg_muted + """;
                background-color: """ + tok.surface_alt + """;
            }}
            MinorEventPushButton[Selected=false]:flat:!pressed:hover {{
                color: """ + tok.fg_secondary + """;
                background-color: """ + tok.border + """;
            }}
            MinorEventPushButton[Selected=false]:flat:pressed {{
                color: """ + tok.fg_secondary + """;
                background-color: """ + tok.border_strong + """;
            }}

            AuxEventPushButton[Selected=false]:pressed {{
                background-color:""" + createGradient(tok.fg_muted) + """ ;
            }}
            AuxEventPushButton[Selected=false]:!pressed:hover {{
                background-color:""" + createGradient(tok.fg_secondary) + """ ;
            }}
"""
    )
