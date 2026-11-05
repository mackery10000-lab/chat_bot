param([string]$ReferenceDirectory = '.local')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$root = Split-Path -Parent $PSScriptRoot
$images = Join-Path $root 'public/assets/images'
$scenes = Join-Path $images 'scenes'
[void][IO.Directory]::CreateDirectory($scenes)

# Backgrounds are the supplied files, copied without resampling or regeneration.
$sources = @{
    'car2' = 'reference-06.png'
    'car3' = 'reference-05.png'
    'engine' = 'reference-07.png'
    'crew' = 'reference-08.png'
    'crew-door' = 'reference-09.png'
}
foreach ($name in $sources.Keys) {
    $reference = Join-Path $root "$ReferenceDirectory/$($sources[$name])"
    $destination = Join-Path $scenes "$name.png"
    if (Test-Path -LiteralPath $reference) {
        Copy-Item -LiteralPath $reference -Destination $destination -Force
    } elseif (-not (Test-Path -LiteralPath $destination)) {
        throw "Missing supplied background: $reference"
    }
}

# Native pixel coordinates. Full-canvas transparent images share the exact
# dimensions and origin of their background, including transparent margins.
$definitions = @(
    @{id='window'; scene='car1/background'; polygon=@(219,293,228,296,344,341,345,504,216,506,214,495,217,337)}
    @{id='notice'; scene='car1/background'; polygon=@(475,399,616,399,626,407,626,479,619,489,474,489,466,480,466,408)}
    @{id='explorer'; scene='scenes/car2'; polygon=@(318,292,336,285,354,287,368,293,380,300,391,314,399,332,401,350,396,373,390,384,381,393,373,399,368,405,379,416,394,428,405,447,417,464,433,477,458,485,473,500,486,520,488,536,481,551,466,564,458,566,463,581,469,600,475,625,479,643,476,658,470,666,467,691,472,710,472,728,477,743,487,768,493,788,496,809,493,823,484,828,469,832,448,829,426,824,415,814,412,796,409,780,395,778,378,774,369,766,350,757,332,751,317,751,304,758,289,757,273,747,253,742,229,737,207,733,187,725,164,712,148,697,138,676,135,654,139,633,148,623,149,613,146,599,147,580,151,557,146,542,153,517,158,492,167,465,175,445,187,428,197,409,208,397,208,362,233,358,235,381,254,370,277,368,292,372,293,349,296,330,307,308)}
    @{id='cleaner'; scene='scenes/car3'; polygon=@(350,254,371,257,392,270,403,292,405,312,398,333,410,349,425,365,440,387,453,412,460,439,460,458,450,481,449,503,458,531,458,557,446,578,448,610,441,652,442,697,429,735,439,753,437,769,416,774,389,769,372,760,364,748,352,765,338,776,309,778,288,769,290,752,305,737,303,700,296,660,287,622,281,587,280,552,273,535,279,510,279,476,279,450,281,417,285,394,295,371,309,355,322,344,320,325,319,302,324,281,334,265)}
    @{id='elder'; scene='scenes/car3'; polygon=@(913,410,936,402,957,408,974,403,994,411,1005,426,1010,443,1009,461,1025,481,1034,511,1041,532,1042,555,1036,576,1048,587,1056,595,1062,615,1064,640,1062,656,1017,654,978,652,936,650,910,644,879,644,864,649,850,647,847,632,831,628,816,622,807,615,802,602,798,582,803,558,813,531,821,502,835,477,853,459,876,447,891,438,898,421)}
    @{id='report'; scene='scenes/crew'; polygon=@(239,966,306,947,488,953,499,961,452,997,431,1017,231,1008,231,995)}
    @{id='desk'; scene='scenes/crew'; polygon=@(400,902,473,899,560,901,563,915,540,935,395,936,393,926)}
    @{id='control'; scene='scenes/engine'; polygon=@(1243,550,1665,500,1717,512,1725,530,1724,816,1729,832,1730,853,1717,883,1696,899,1696,925,1723,937,1734,947,1737,965,1738,1006,1717,1018,1685,1020,1639,1014,1593,1000,1585,983,1290,944,1290,927,1242,924,1242,908,1233,903,1233,881,1230,860,1238,814,1246,784,1244,735)}
    @{id='engine-lever'; scene='scenes/engine'; polygon=@(1677,621,1693,624,1708,636,1712,657,1707,680,1698,710,1693,748,1702,790,1722,819,1730,838,1730,854,1718,880,1692,894,1694,925,1723,937,1734,947,1737,965,1738,1006,1717,1018,1685,1020,1639,1014,1593,1000,1585,983,1587,967,1598,951,1597,936,1621,926,1629,914,1629,882,1613,868,1605,850,1603,832,1610,817,1627,801,1636,757,1649,743,1652,700,1656,669,1656,646,1663,631)}
    @{id='crew_door'; scene='scenes/crew-door'; polygon=@(626,60,1140,61,1146,1134,625,1134)}
    @{id='inspection_cover'; scene='scenes/crew-door'; polygon=@(1265,782,1515,782,1533,799,1534,1049,1519,1067,1267,1067,1251,1050,1251,799)}
    @{id='door_handle'; scene='scenes/crew-door'; polygon=@(646,595,678,593,692,607,693,638,756,650,770,658,769,666,755,674,694,675,693,748,681,759,649,757,637,746,638,609)}
)
$manifest = @{}
foreach ($entry in $definitions) {
    $sourcePath = Join-Path $images ($entry.scene + '.png')
    $source = [Drawing.Bitmap]::new($sourcePath)
    $canvas = [Drawing.Bitmap]::new($source.Width, $source.Height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($canvas)
    $graphics.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::None
    $shape = [Drawing.Drawing2D.GraphicsPath]::new()
    $points = [Collections.Generic.List[Drawing.PointF]]::new()
    $normalized = @()
    for ($i=0; $i -lt $entry.polygon.Count; $i+=2) {
        $x=$entry.polygon[$i]; $y=$entry.polygon[$i+1]
        $points.Add([Drawing.PointF]::new($x,$y))
        $normalized += ,@([math]::Round($x*100/$source.Width,6),[math]::Round($y*100/$source.Height,6))
    }
    $shape.AddPolygon($points.ToArray())
    $graphics.SetClip($shape)
    $graphics.DrawImageUnscaled($source,0,0)
    $sceneName = ($entry.scene -split '/')[-1]
    if ($sceneName -eq 'background') { $sceneName='car1' }
    $output = "$sceneName-$($entry.id).png"
    $canvas.Save((Join-Path $scenes $output),[Drawing.Imaging.ImageFormat]::Png)
    $xs=@($points | ForEach-Object X); $ys=@($points | ForEach-Object Y)
    $minX=($xs | Measure-Object -Minimum).Minimum; $maxX=($xs | Measure-Object -Maximum).Maximum
    $minY=($ys | Measure-Object -Minimum).Minimum; $maxY=($ys | Measure-Object -Maximum).Maximum
    $manifest["$sceneName.$($entry.id)"] = @{
        image="/assets/images/scenes/$output"
        background="/assets/images/$($entry.scene).png"
        size=@($source.Width,$source.Height)
        polygon=$normalized
        bounds=@(($minX*100/$source.Width),($minY*100/$source.Height),(($maxX-$minX)*100/$source.Width),(($maxY-$minY)*100/$source.Height))
    }
    $shape.Dispose(); $graphics.Dispose(); $canvas.Dispose(); $source.Dispose()
}
$json = $manifest | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText((Join-Path $scenes 'registration.json'),$json,[Text.UTF8Encoding]::new($false))
Write-Output "Saved $($sources.Count) original backgrounds and $($definitions.Count) registered transparent layers."
