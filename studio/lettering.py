"""Instructions for model-rendered lettering; exact overlays stay separate."""
import json

STYLES = {
    'ice': 'elegant sculpted ice lettering, frosted edges, pale blue and silver highlights, subtle snowflake ornamentation',
    'ribbon': 'playful hand-lettered calligraphy on a beautiful curved ribbon banner, harmonized with the scene colors',
    'gold': 'luxurious embossed gold calligraphy, dimensional letters with realistic light and shadow',
}
MODES = ('overlay', 'styled', 'integrated')

def generation_prompt(settings):
    prompt = settings['prompt']
    if settings.get('text_mode', 'overlay') != 'integrated' or not settings.get('text', '').strip():
        return prompt
    style = STYLES[settings.get('text_style', 'ice')]
    detail = settings.get('text_style_detail', '').strip()
    message = json.dumps(settings['text'], ensure_ascii=False)
    position = settings.get('text_position', 'bottom')
    return (f'{prompt}\n\nLETTERING AND COMPOSITION: Include the exact message {message} as an integral part '
            f'of the artwork, designed into the {position} part of the scene. Use {style}. '
            f'{detail} The letters belong to a physical decorative sign or scene element, with coherent '
            'lighting, perspective, and materials; compose the scene around the lettering. '
            'Make it prominent, legible, and elegant without covering the characters. '
            'Copy the supplied characters and number exactly; do not translate the message. '
            'For Hebrew use correctly ordered right-to-left words. This lettering instruction replaces '
            'any earlier instruction to omit text or leave the message area blank. Do not add other writing.')

def print_text(settings):
    return '' if settings.get('text_mode', 'overlay') == 'integrated' else settings.get('text', '')
