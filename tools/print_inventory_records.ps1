# Print only the right-hand record pages. Book, item art and controls stay intact.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class RecordInk {
    public static int[] Finish(Bitmap image) {
        var rect=new Rectangle(0,0,image.Width,image.Height);
        var data=image.LockBits(rect,ImageLockMode.ReadWrite,PixelFormat.Format32bppArgb);
        int left=image.Width,top=image.Height,right=0,bottom=0;
        try {
            var bytes=new byte[data.Stride*image.Height];
            Marshal.Copy(data.Scan0,bytes,0,bytes.Length);
            var random=new Random(132026);
            for(int y=0;y<image.Height;y++) for(int x=0;x<image.Width;x++) {
                int at=y*data.Stride+x*4;
                if(bytes[at+3]==0) continue;
                // Mild ribbon wear belongs to the printed ink, never the paper.
                double wear=random.NextDouble();
                if(wear<.022) bytes[at+3]=(byte)(bytes[at+3]*.42);
                else if(wear<.14) bytes[at+3]=(byte)(bytes[at+3]*.78);
                if(bytes[at+3]>8) {left=Math.Min(left,x);top=Math.Min(top,y);right=Math.Max(right,x);bottom=Math.Max(bottom,y);}
            }
            Marshal.Copy(bytes,0,data.Scan0,bytes.Length);
        } finally {image.UnlockBits(data);}
        return new [] {left,top,right+1,bottom+1};
    }
}
'@
$root=Split-Path -Parent $PSScriptRoot
$assets=Join-Path $root 'public/assets/images/inventory'
$source=Get-Content -Encoding UTF8 -Raw -LiteralPath (Join-Path $assets 'print-source.json') | ConvertFrom-Json
$output=Join-Path $assets 'records'
$staging=Join-Path $root '.local/inventory-record-build'
[void][IO.Directory]::CreateDirectory($output)
[void][IO.Directory]::CreateDirectory($staging)
$fonts=[Drawing.Text.PrivateFontCollection]::new()
$fonts.AddFontFile((Join-Path $root 'public/assets/css/NanumMyeongjo-ExtraBold.ttf'))
$family=$fonts.Families[0]
$ink=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(233,47,40,29))
$muted=[Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(205,65,55,39))
$rule=[Drawing.Pen]::new([Drawing.Color]::FromArgb(112,78,62,40),1.3)
$heavyRule=[Drawing.Pen]::new([Drawing.Color]::FromArgb(173,65,52,34),2.2)
$format=[Drawing.StringFormat]::GenericTypographic.Clone()
$format.FormatFlags=$format.FormatFlags -bor [Drawing.StringFormatFlags]::MeasureTrailingSpaces
$script:drawn=[Collections.Generic.List[object]]::new()

function New-RecordFont([double]$size) {
    return [Drawing.Font]::new($family,$size,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
}
function Get-RecordLines([string]$text,$font,[double]$width) {
    $lines=[Collections.Generic.List[string]]::new()
    foreach($paragraph in ($text -split "`n")) {
        $line=''
        foreach($word in ($paragraph -split '\s+')) {
            if(!$word.Length){continue}
            $trial=if($line.Length){$line+' '+$word}else{$word}
            if($line.Length -and $g.MeasureString($trial,$font,[Drawing.PointF]::new(0,0),$format).Width -gt $width){$lines.Add($line);$line=$word}
            else{$line=$trial}
        }
        if($line.Length){$lines.Add($line)}
    }
    return ,$lines.ToArray()
}
function Write-RecordText([string]$text,[double]$x,[double]$y,[double]$width,[double]$size,[double]$leading,$brush=$ink) {
    $font=New-RecordFont $size
    $start=$y
    foreach($line in (Get-RecordLines $text $font $width)) {
        $extent=$g.MeasureString($line,$font,[Drawing.PointF]::new(0,0),$format)
        if($extent.Width -gt ($width+1)){throw "Unbreakable text exceeds its cell: $line"}
        $g.DrawString($line,$font,$brush,[Drawing.PointF]::new($x,$y),$format)
        $script:drawn.Add(@{text=$line;x=$x;y=$y;width=[Math]::Round($extent.Width,2);size=$size;leading=$leading})
        $y+=$leading
    }
    $font.Dispose()
    return $y-$start
}
function Measure-RecordText([string]$text,[double]$width,[double]$size,[double]$leading) {
    $font=New-RecordFont $size
    $height=(Get-RecordLines $text $font $width).Count*$leading
    $font.Dispose()
    return $height
}
function Write-RecordRule([double]$y,[bool]$heavy=$false) {
    $pen=if($heavy){$heavyRule}else{$rule}
    $g.DrawLine($pen,32,[single]$y,868,[single]$y)
}
function Write-RecordParagraph([string]$text,[double]$y,[double]$size=34,[double]$leading=45) {
    return (Write-RecordText $text 46 $y 808 $size $leading)+14
}
function Write-RecordFields($fields,[double]$y,[double]$size=34,[double]$leading=44) {
    $start=$y
    foreach($field in $fields) {
        $labelHeight=Measure-RecordText ([string]$field[0]) 242 $size $leading
        $valueHeight=Measure-RecordText ([string]$field[1]) 528 $size $leading
        $height=[Math]::Max(59,[Math]::Max($labelHeight,$valueHeight)+18)
        Write-RecordRule $y
        [void](Write-RecordText ([string]$field[0]) 48 ($y+9) 242 $size $leading)
        [void](Write-RecordText ([string]$field[1]) 320 ($y+9) 528 $size $leading)
        $g.DrawLine($rule,302,[single]$y,302,[single]($y+$height))
        $y+=$height
    }
    Write-RecordRule $y
    return $y-$start
}
function Write-RecordSteps($paragraphs,[double]$y,[bool]$report=$false) {
    $start=$y
    foreach($paragraph in $paragraphs) {
        if($report) {
            $parts=[regex]::Match([string]$paragraph,'^(\d+)\. (.+?) — (.+)$')
            $label=$parts.Groups[1].Value+".`n"+$parts.Groups[2].Value
            $text=$parts.Groups[3].Value
            $height=[Math]::Max((Measure-RecordText $text 628 30 39),(Measure-RecordText $label 140 26 34))+15
            Write-RecordRule $y
            [void](Write-RecordText $label 44 ($y+10) 140 26 34)
            [void](Write-RecordText $text 218 ($y+10) 628 30 39)
            $g.DrawLine($rule,198,[single]$y,198,[single]($y+$height))
        }else {
            $parts=[regex]::Match([string]$paragraph,'^(\d+)\. (.+)$')
            $text=$parts.Groups[2].Value
            $height=(Measure-RecordText $text 724 33 44)+24
            Write-RecordRule $y
            [void](Write-RecordText ($parts.Groups[1].Value+'.') 46 ($y+12) 55 34 44)
            [void](Write-RecordText $text 122 ($y+12) 724 33 44)
        }
        $y+=$height
    }
    Write-RecordRule $y
    return $y-$start
}

$manifest=[ordered]@{canvas=@(900,1120);font='Nanum Myeongjo ExtraBold';contentBottom=730;records=[ordered]@{}}
foreach($doc in $source.records) {
    $filename=[IO.Path]::GetFileName($doc.artwork)
    $bitmap=[Drawing.Bitmap]::new(900,1120,[Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g=[Drawing.Graphics]::FromImage($bitmap)
    $g.TextRenderingHint=[Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::HighQuality
    $script:drawn.Clear()
    $y=28.0
    $title=[string]$doc.title
    $titleSize=50.0;$titleLeading=64.0
    if($doc.id -eq 'route_report'){$title="2016년 아지산역`n폐쇄 예정 및 선로 통제 보고서";$titleSize=43;$titleLeading=54}
    elseif($doc.id -eq 'newspaper'){$title="23시 59분 출발 열차,`n흔적도 없이 사라져";$titleSize=45;$titleLeading=56}
    elseif($doc.id -eq 'facility_manual'){$title='전자 잠금장치 오류 발생 시';$titleSize=45;$titleLeading=58}
    $y+=Write-RecordText $title 42 $y 816 $titleSize $titleLeading
    $y+=12;Write-RecordRule $y $true;$y+=24
    switch([string]$doc.id) {
        'route_report' {
            $y+=Write-RecordSteps $doc.paragraphs $y $true
        }
        'facility_manual' {
            $y+=Write-RecordParagraph ([string]$doc.paragraphs[0]) $y 32 42
            $y+=8
            $y+=Write-RecordSteps @($doc.paragraphs | Select-Object -Skip 1) $y
        }
        'flashlight' {
            $sentences=[regex]::Split([string]$doc.paragraphs[0],'(?<=\.)\s+')
            foreach($i in 0..($sentences.Count-1)) {
                $label=if($i -eq 0){'용도'}else{'사용 방법'}
                [void](Write-RecordText $label 46 $y 808 30 41 $muted);$y+=45
                $y+=Write-RecordParagraph $sentences[$i] $y 36 48
                $y+=10;Write-RecordRule $y;$y+=24
            }
        }
        'elder_testimony' {
            foreach($paragraph in $doc.paragraphs) {
                $feature=([string]$paragraph).StartsWith('승차권은')
                $labels=if($feature){@('승차권 외형','분실 경위')}else{@('목적지 기억','이름의 유래')}
                $sentences=[regex]::Split([string]$paragraph,'(?<=\.)\s+')
                foreach($i in 0..($sentences.Count-1)) {
                    [void](Write-RecordText $labels[$i] 46 $y 808 28 38 $muted);$y+=39
                    $y+=Write-RecordParagraph $sentences[$i] $y 34 44
                    Write-RecordRule $y;$y+=18
                }
            }
        }
        default {
            $summary=([string]$doc.paragraphs[0]) -replace '(?<=\.)\s+',"`n"
            $size=if($doc.id -eq 'newspaper'){32}else{34}
            $leading=if($doc.id -eq 'newspaper'){42}else{45}
            $y+=Write-RecordParagraph $summary $y $size $leading
            if($doc.id -eq 'newspaper') {
                $y+=Write-RecordParagraph ([string]$doc.paragraphs[1]) $y $size $leading
            }
            $y+=12
            $y+=Write-RecordFields $doc.fields $y 33 43
            if($filename -eq 'ticket-old-returned.png') {
                $y+=22
                $y+=Write-RecordParagraph ([string]$doc.paragraphs[1]) $y 29 39
            }
        }
    }
    $g.Dispose()
    $bounds=[RecordInk]::Finish($bitmap)
    if($bounds[3] -gt 730){$bitmap.Dispose();throw "Printed record exceeds the reserved content area: $filename ($($bounds[3]))"}
    $bitmap.Save((Join-Path $staging $filename),[Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    $manifest.records[$filename]=@{inkBounds=$bounds;lines=@($script:drawn.ToArray());documentId=$doc.id}
    Write-Output "$filename : ink ends at $($bounds[3])/1120 px"
}
foreach($filename in $manifest.records.Keys){Copy-Item -LiteralPath (Join-Path $staging $filename) -Destination (Join-Path $output $filename)}
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $output 'layout-manifest.json') -Encoding UTF8
$fonts.Dispose();$ink.Dispose();$muted.Dispose();$rule.Dispose();$heavyRule.Dispose();$format.Dispose()
Write-Output "Printed $($manifest.records.Count) records. Book, item and action images were not modified."
