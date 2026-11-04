$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class ArchiveBitmap {
    public static Bitmap Trim(string path) {
        using(var source=new Bitmap(path)) {
            var rect=new Rectangle(0,0,source.Width,source.Height);
            var data=source.LockBits(rect,ImageLockMode.ReadOnly,PixelFormat.Format32bppArgb);
            int left=source.Width,top=source.Height,right=0,bottom=0;
            try {
                var bytes=new byte[data.Stride*source.Height]; Marshal.Copy(data.Scan0,bytes,0,bytes.Length);
                for(int y=0;y<source.Height;y++) for(int x=0;x<source.Width;x++)
                    if(bytes[y*data.Stride+x*4+3]>10) {left=Math.Min(left,x);right=Math.Max(right,x);top=Math.Min(top,y);bottom=Math.Max(bottom,y);}
            } finally {source.UnlockBits(data);}
            return source.Clone(new Rectangle(left,top,right-left+1,bottom-top+1),PixelFormat.Format32bppArgb);
        }
    }
    public static void Wear(Bitmap image, int seed) {
        var random=new Random(seed);
        var rect=new Rectangle(0,0,image.Width,image.Height);
        var data=image.LockBits(rect,ImageLockMode.ReadWrite,PixelFormat.Format32bppArgb);
        try {
            var bytes=new byte[data.Stride*image.Height];Marshal.Copy(data.Scan0,bytes,0,bytes.Length);
            for(int i=0;i<bytes.Length;i+=4) if(bytes[i+3]>0) {
                if(random.NextDouble()<0.018) bytes[i+3]=(byte)(bytes[i+3]*.4);
                else if(random.NextDouble()<0.12) bytes[i+3]=(byte)(bytes[i+3]*.82);
            }
            Marshal.Copy(bytes,0,data.Scan0,bytes.Length);
        } finally {image.UnlockBits(data);}
    }
}
'@
$root=Split-Path -Parent $PSScriptRoot
$assets=Join-Path $root 'public/assets/images/inventory'
$source=Get-Content -Encoding UTF8 -Raw -LiteralPath (Join-Path $assets 'print-source.json') | ConvertFrom-Json
$records=Join-Path $assets 'records'; $actions=Join-Path $assets 'actions'
[void][IO.Directory]::CreateDirectory($records); [void][IO.Directory]::CreateDirectory($actions)
$book=[Drawing.Bitmap]::new((Join-Path $assets 'book-detail.png'))
$left=[int]($book.Width*0.495)
$singlePage=$book.Clone([Drawing.Rectangle]::new($left,0,($book.Width-$left),$book.Height),[Drawing.Imaging.PixelFormat]::Format32bppArgb)
$singlePage.Save((Join-Path $assets 'record-paper.png'),[Drawing.Imaging.ImageFormat]::Png)
$singlePage.Dispose();$book.Dispose()
$fonts=[Drawing.Text.PrivateFontCollection]::new()
$fonts.AddFontFile((Join-Path $root 'public/assets/css/D2Coding-Regular.ttf'))
$family=$fonts.Families[0]
$ink=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(235,48,43,34))
$rule=[Drawing.Pen]::new([Drawing.Color]::FromArgb(85,91,75,51),1.5)
$format=[Drawing.StringFormat]::GenericTypographic.Clone()
$format.FormatFlags=$format.FormatFlags -bor [Drawing.StringFormatFlags]::MeasureTrailingSpaces

function New-PageGraphics($bitmap) {
    $g=[Drawing.Graphics]::FromImage($bitmap)
    $g.TextRenderingHint=[Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::HighQuality
    return $g
}
function Get-Lines($g,[string]$text,$font,[double]$width) {
    $lines=[Collections.Generic.List[string]]::new(); $line=''
    foreach($word in ($text -split '\s+')) {
        $trial=if($line.Length){$line+' '+$word}else{$word}
        if($line.Length -gt 0 -and $g.MeasureString($trial,$font,[Drawing.PointF]::new(0,0),$format).Width -gt $width){$lines.Add($line);$line=$word}
        else {$line=$trial}
    }
    if($line.Length){$lines.Add($line.TrimEnd())}
    return ,$lines.ToArray()
}
function Measure-Record($g,$doc,$size) {
    $font=[Drawing.Font]::new($family,$size,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
    $title=[Drawing.Font]::new($family,($size*1.34),[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
    $height=90+(Get-Lines $g $doc.title $title 832).Count*($size*1.7)+32
    foreach($paragraph in $doc.paragraphs){$height+=(Get-Lines $g $paragraph $font 832).Count*($size*1.55)+22}
    if($doc.fields.Count){$height+=26+$doc.fields.Count*($size*2.15)}
    $font.Dispose();$title.Dispose();return $height
}
$index=0
foreach($doc in $source.records) {
    $bitmap=[Drawing.Bitmap]::new(900,1120,[Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g=New-PageGraphics $bitmap
    $size=34
    while((Measure-Record $g $doc $size) -gt 1020 -and $size -gt 27){$size-=1}
    if((Measure-Record $g $doc $size) -gt 1020){throw "Record too long: $($doc.id)"}
    $body=[Drawing.Font]::new($family,$size,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
    $title=[Drawing.Font]::new($family,($size*1.34),[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
    $small=[Drawing.Font]::new($family,21,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
    $g.DrawString([string]$doc.eyebrow,$small,$ink,[Drawing.PointF]::new(34,27),$format)
    $y=87.0
    foreach($line in (Get-Lines $g $doc.title $title 832)) {
        $g.DrawString($line,$title,$ink,[Drawing.PointF]::new(34,$y),$format);$y+=$size*1.7
    }
    $y+=13;$g.DrawLine($rule,34,[single]$y,866,[single]$y);$y+=28
    foreach($paragraph in $doc.paragraphs) {
        foreach($line in (Get-Lines $g $paragraph $body 832)) {
            $g.DrawString($line,$body,$ink,[Drawing.PointF]::new(34,$y),$format);$y+=$size*1.55
        }
        $y+=22
    }
    if($doc.fields.Count) {
        $y+=15;$rowHeight=$size*2.15
        foreach($field in $doc.fields) {
            $g.DrawLine($rule,34,[single]$y,866,[single]$y)
            $g.DrawString([string]$field[0],$body,$ink,[Drawing.PointF]::new(48,($y+16)),$format)
            $g.DrawString([string]$field[1],$body,$ink,[Drawing.PointF]::new(350,($y+16)),$format)
            $g.DrawLine($rule,330,[single]$y,330,[single]($y+$rowHeight))
            $y+=$rowHeight
        }
        $g.DrawLine($rule,34,[single]$y,866,[single]$y)
    }
    $g.DrawString('13-FRI  /  INVESTIGATION ARCHIVE',$small,$ink,[Drawing.PointF]::new(34,1070),$format)
    $g.Dispose();[ArchiveBitmap]::Wear($bitmap,2016+$index)
    $filename=[IO.Path]::GetFileName($doc.artwork)
    $bitmap.Save((Join-Path $records $filename),[Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose();$body.Dispose();$title.Dispose();$small.Dispose();$index++
}

# Rasterize every action label onto the generated dark paper; no live text
# overlays or separately scrolling text are used by these buttons.
$blank=[ArchiveBitmap]::Trim((Join-Path $assets 'action-blank.png'))
$blank.Save((Join-Path $assets 'action-paper.png'),[Drawing.Imaging.ImageFormat]::Png)
foreach($entry in $source.actions.PSObject.Properties) {
    $buttonWidth=if($entry.Name -in @('previous','next')){300}else{960}
    $buttonHeight=if($entry.Name -in @('previous','next')){140}else{160}
    $button=[Drawing.Bitmap]::new($buttonWidth,$buttonHeight,[Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g=New-PageGraphics $button
    $g.InterpolationMode=[Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($blank,0,0,$buttonWidth,$buttonHeight)
    $size=42
    $font=[Drawing.Font]::new($family,$size,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
    while($g.MeasureString([string]$entry.Value,$font).Width -gt ($buttonWidth-110)){$font.Dispose();$size-=1;$font=[Drawing.Font]::new($family,$size,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)}
    $align=[Drawing.StringFormat]::new();$align.Alignment=[Drawing.StringAlignment]::Center;$align.LineAlignment=[Drawing.StringAlignment]::Center
    $label=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(245,222,207,171))
    $g.DrawString([string]$entry.Value,$font,$label,[Drawing.RectangleF]::new(45,13,($buttonWidth-90),($buttonHeight-26)),$align)
    $g.Dispose();$font.Dispose();$label.Dispose();$align.Dispose()
    $button.Save((Join-Path $actions ($entry.Name+'.png')),[Drawing.Imaging.ImageFormat]::Png);$button.Dispose()
}
$blank.Dispose();$ink.Dispose();$rule.Dispose();$format.Dispose();$fonts.Dispose()
Write-Output "Printed $index state-specific record PNGs and $(@($source.actions.PSObject.Properties).Count) action PNGs."
