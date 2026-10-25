"""A4 exports and editable exact-text layers; all rendering is local."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from studio.styled_text import styled_banner, visual_text, letter_color, lettering_font, load_lettering_font, outline_width, font_points

A4 = (2480, 3508)
FONT = Path('/System/Library/Fonts/Supplemental/Arial.ttf')

def plain_layer(text, max_width, color='', font_choice='classic', stroke_width=None, stroke_color='', font_size_pt=None):
    stroke=5 if stroke_width is None else stroke_width
    text=visual_text(text)
    draw=ImageDraw.Draw(Image.new('L',(1,1)))
    for font_size in ([round(font_size_pt*300/72)] if font_size_pt is not None else range(180,23,-4)):
        font=(ImageFont.truetype(str(FONT),font_size) if FONT.exists() else ImageFont.load_default(font_size)) if font_choice=='classic' else load_lettering_font(font_choice,font_size)
        box=draw.multiline_textbbox((0,0),text,font=font,align='center',stroke_width=stroke)
        if box[2]-box[0]<=max_width-100 and box[3]-box[1]<=1000:
            break
    else:
        raise ValueError('Message is too long. Shorten it or add line breaks.')
    layer=Image.new('RGBA',(box[2]-box[0]+40,box[3]-box[1]+40))
    ImageDraw.Draw(layer).multiline_text((20-box[0],20-box[1]),text,font=font,fill=color or '#183862',stroke_width=stroke,stroke_fill=stroke_color or 'white',align='center')
    return layer

def export_print(source: Path, destination: Path, orientation='portrait', text='', position='bottom', margin_mm=5,
                 text_mode='overlay', text_style='ice', text_background='banner', text_scale=1.0, text_x=None, text_y=None, text_color='', text_font='classic', text_outline_width=None, text_outline_color='', text_font_size=None):
    text_color=letter_color(text_color)
    text_font=lettering_font(text_font)
    text_outline_width=outline_width(text_outline_width)
    text_outline_color=letter_color(text_outline_color)
    text_font_size=font_points(text_font_size)
    size=(2362,2362) if orientation=='square20' else A4 if orientation=='portrait' else A4[::-1]
    margin=round(margin_mm*300/25.4)
    with Image.open(source) as image:
        image=ImageOps.exif_transpose(image).convert('RGB')
        fitted=ImageOps.contain(image,(size[0]-2*margin,size[1]-2*margin),Image.Resampling.LANCZOS)
    page=Image.new('RGB',size,'white')
    page.paste(fitted,((size[0]-fitted.width)//2,(size[1]-fitted.height)//2))
    page.save(destination/'a4-base.png',dpi=(300,300))
    layout=dict(editable=False,page_width=size[0],page_height=size[1],margin=margin)
    if text.strip() and text_mode!='integrated':
        layer=(styled_banner(text,size[0]-2*margin-80,text_style,background=text_background=='banner',color=text_color,font_choice=text_font,stroke_width=text_outline_width,stroke_color=text_outline_color,font_size_pt=text_font_size)
               if text_mode=='styled' else plain_layer(text,size[0]-2*margin,text_color,text_font,text_outline_width,text_outline_color,text_font_size))
        fit=min(float(text_scale),(size[0]-2*margin)/layer.width,(size[1]-2*margin)/layer.height)
        layer=layer.resize((max(1,round(layer.width*fit)),max(1,round(layer.height*fit))),Image.Resampling.LANCZOS)
        left=(size[0]-layer.width)//2
        top=margin+35 if position=='top' else ((size[1]-layer.height)//2 if position=='center' else size[1]-margin-layer.height-35)
        if text_x is not None:
            left=round(text_x*size[0]-layer.width/2)
        if text_y is not None:
            top=round(text_y*size[1]-layer.height/2)
        left=max(margin,min(left,size[0]-margin-layer.width))
        top=max(margin,min(top,size[1]-margin-layer.height))
        layer.save(destination/'lettering.png')
        page.paste(layer,(left,top),layer)
        layout.update(editable=True,x=left,y=top,width=layer.width,height=layer.height,scale=float(text_scale),
                      center_x=(left+layer.width/2)/size[0],center_y=(top+layer.height/2)/size[1])
    else:
        (destination/'lettering.png').unlink(missing_ok=True)
    (destination/'lettering-layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    page.save(destination/'a4.png',dpi=(300,300))
    mm=(200,200) if orientation=='square20' else (210,297) if orientation=='portrait' else (297,210)
    page.save(destination/'a4.pdf','PDF',dpi=(size[0]*25.4/mm[0],size[1]*25.4/mm[1]))
    return size
