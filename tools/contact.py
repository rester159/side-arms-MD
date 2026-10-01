import sys
from pathlib import Path
from PIL import Image
files=sorted(Path(sys.argv[1]).glob('*.png'))[::int(sys.argv[3]) if len(sys.argv)>3 else 1]
w,h=files[0].open if False else Image.open(files[0]).size
cols=6;s=0.5;tw,th=int(w*s),int(h*s);rows=(len(files)+cols-1)//cols
sheet=Image.new('RGB',(cols*tw,rows*th))
for i,f in enumerate(files):sheet.paste(Image.open(f).convert('RGB').resize((tw,th)),((i%cols)*tw,(i//cols)*th))
sheet.save(sys.argv[2]);print(len(files),sheet.size)
