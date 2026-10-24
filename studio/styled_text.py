"""Deterministic decorative lettering: real font glyphs, never AI-spelled words."""
from pathlib import Path
import re
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, features

FONT = Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')
FONT_CHOICES = {
    'classic': FONT,
    'rounded': Path(__file__).parent/'fonts/varelaround/VarelaRound-Regular.ttf',
    'handwritten': Path(__file__).parent/'fonts/gveretlevin/GveretLevin-Regular.ttf',
}

def lettering_font(choice='classic'):
    if not isinstance(choice,str) or choice not in FONT_CHOICES:
        raise ValueError('Choose classic, rounded, or handwritten lettering.')
    return choice

def load_lettering_font(choice, size):
    path=FONT_CHOICES[lettering_font(choice)]
    if path.exists():
        return ImageFont.truetype(str(path),size)
    if choice != 'classic':
        raise ValueError('Lettering font is missing. Restore the studio/fonts folder.')
    return ImageFont.load_default(size)

def letter_color(value):
    """Empty means the theme palette; custom colors use unambiguous RGB hex."""
    if value in (None, ''):
        return ''
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Letter color must be a six-digit hex color, such as #E66CA6.')
    return value.upper()

def outline_width(value=None):
    if value in (None,''):
        return None
    if isinstance(value,bool):
        raise ValueError('Outline thickness must be 0–12 pixels.')
    try:
        number=float(value)
    except (TypeError,ValueError):
        raise ValueError('Outline thickness must be 0–12 pixels.') from None
    if not number.is_integer() or not 0<=number<=12:
        raise ValueError('Outline thickness must be 0–12 pixels.')
    return int(number)

def font_points(value=None):
    if value in (None,''):
        return None
    if isinstance(value,bool):
        raise ValueError('Font size must be 8–144 points, or blank for automatic.')
    try:
        size=float(value)
    except (TypeError,ValueError):
        raise ValueError('Font size must be 8–144 points, or blank for automatic.') from None
    if not 8<=size<=144:
        raise ValueError('Font size must be 8–144 points, or blank for automatic.')
    return size

def visual_text(text):
    if features.check('raqm'):
        return text
    if any('\u0600' <= ch <= '\u08ff' for ch in text):
        raise ValueError('This Pillow build lacks Arabic shaping.')
    if any('\u0590' <= ch <= '\u05ff' for ch in text):
        from bidi.algorithm import get_display
        return '\n'.join(get_display(line) for line in text.split('\n'))
    return text

def gradient(size, stops):
    colors=[]
    for y in range(size[1]):
        t=y/max(1,size[1]-1)*(len(stops)-1)
        i=min(int(t),len(stops)-2)
        f=t-i
        colors.append(tuple(round(a+(b-a)*f) for a,b in zip(stops[i],stops[i+1])))
    strip=Image.new('RGB',(1,size[1]))
    strip.putdata(colors)
    return strip.resize(size)

def colored_mask(size, color, mask):
    layer=Image.new('RGBA',size,color)
    layer.putalpha(mask)
    return layer

def styled_banner(text, max_width, style='ice', background=True, color='', font_choice='classic', stroke_width=None, stroke_color='', font_size_pt=None):
    """Return a transparent, print-resolution banner with exact visible lettering."""
    color=letter_color(color)
    font_choice=lettering_font(font_choice)
    stroke=outline_width(stroke_width)
    stroke=(7 if font_choice=='classic' else 2) if stroke is None else stroke
    stroke_color=letter_color(stroke_color)
    points=font_points(font_size_pt)
    text=visual_text(text)
    probe=ImageDraw.Draw(Image.new('L',(1,1)))
    for font_size in ([round(points*300/72)] if points is not None else range(220,27,-4)):
        font=load_lettering_font(font_choice,font_size)
        box=probe.multiline_textbbox((0,0),text,font=font,spacing=14,align='center',stroke_width=stroke)
        if box[2]-box[0]<=max_width-240 and box[3]-box[1]<=650:
            break
    else:
        raise ValueError('Message does not fit. Reduce the font size, shorten it, or add line breaks.')
    width=max_width
    height=box[3]-box[1]+170
    size=(width,height)
    panel=Image.new('RGBA',size)
    draw=ImageDraw.Draw(panel)
    inset=24
    if not background:
        fill_colors = {'ice':[(255,255,255),(159,212,242),(230,249,255),(84,146,193)],
                       'ribbon':[(255,255,255),(243,226,255),(255,255,255)],
                       'gold':[(255,250,207),(253,214,98),(168,104,27),(255,237,161)]}[style]
        outline = {'ice':'#4a789c','ribbon':'#58416f','gold':'#78501b'}[style]
    elif style=='ribbon':
        draw.polygon([(0,60),(130,90),(130,height-80),(0,height-45),(50,height//2)],fill='#7760a0')
        draw.polygon([(width,60),(width-130,90),(width-130,height-80),(width,height-45),(width-50,height//2)],fill='#7760a0')
        draw.rounded_rectangle((95,30,width-95,height-35),radius=45,fill=(97,72,143,245),outline=(235,224,255,255),width=5)
        draw.line((120,55,width-120,55),fill='#cdbbea',width=3)
        fill_colors=[(255,255,255),(243,226,255),(255,255,255)]
        outline='#58416f'
    elif style=='gold':
        draw.rounded_rectangle((inset,inset,width-inset,height-inset),radius=65,fill=(52,38,60,218),outline='#efc86c',width=5)
        draw.rounded_rectangle((inset+14,inset+14,width-inset-14,height-inset-14),radius=51,outline=(255,233,173,170),width=2)
        fill_colors=[(255,250,207),(253,214,98),(168,104,27),(255,237,161)]
        outline='#78501b'
    else:
        draw.rounded_rectangle((inset,inset,width-inset,height-inset),radius=65,fill=(222,243,255,224),outline=(255,255,255,255),width=6)
        draw.rounded_rectangle((inset+14,inset+14,width-inset-14,height-inset-14),radius=51,outline=(114,170,203,170),width=3)
        fill_colors=[(255,255,255),(159,212,242),(230,249,255),(84,146,193)]
        outline='#4a789c'
        # Ornament stays beside the glyphs; it never changes their shapes.
        for cx in (77,width-77):
            cy=height//2
            for dx,dy in ((0,35),(30,18),(30,-18)):
                draw.line((cx-dx,cy-dy,cx+dx,cy+dy),fill=(255,255,255,245),width=5)
    if color:
        rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
        def tint(white):
            return tuple(round(c+(255-c)*white) if white>=0 else round(c*(1+white)) for c in rgb)
        # Retain the theme's material contrast, glyphs and bevel; recolor letters only.
        stops={'ice':(.85,.2,.65,-.2),'ribbon':(.75,.1,.7),'gold':(.7,.05,-.3,.5)}[style]
        fill_colors=[tint(v) for v in stops]
        outline=tint(-.55)
    outline=stroke_color or outline
    x=(width-(box[2]-box[0]))/2-box[0]
    y=(height-(box[3]-box[1]))/2-box[1]-3
    mask=Image.new('L',size)
    mask_draw=ImageDraw.Draw(mask)
    mask_draw.multiline_text((x,y),text,font=font,spacing=14,align='center',fill=255)
    outline_mask=Image.new('L',size)
    ImageDraw.Draw(outline_mask).multiline_text((x,y),text,font=font,spacing=14,align='center',fill=255,stroke_width=stroke,stroke_fill=255)
    classic=font_choice=='classic'
    shadow=ImageChops.offset(outline_mask,5 if classic else 1,10 if classic else 3).filter(ImageFilter.GaussianBlur(8 if classic else 3)).point(lambda a:a*(120 if classic else 65)//255)
    panel=Image.alpha_composite(panel,colored_mask(size,(30,43,69),shadow))
    panel=Image.alpha_composite(panel,colored_mask(size,outline,outline_mask))
    fill=gradient(size,fill_colors).convert('RGBA')
    fill.putalpha(mask)
    panel=Image.alpha_composite(panel,fill)
    if not classic:
        return panel
    highlights=ImageChops.subtract(mask,ImageChops.offset(mask,3,4)).point(lambda a:a*190//255)
    lowlights=ImageChops.subtract(mask,ImageChops.offset(mask,-3,-4)).point(lambda a:a*80//255)
    panel=Image.alpha_composite(panel,colored_mask(size,'white',highlights))
    panel=Image.alpha_composite(panel,colored_mask(size,outline,lowlights))
    return panel
