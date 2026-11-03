$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class PixelRegistration {
    public static long Check(string scene, string mask) {
        using (var a=new Bitmap(scene)) using (var b=new Bitmap(mask)) {
            if(a.Size!=b.Size) throw new Exception("Canvas mismatch: "+mask);
            var rect=new Rectangle(0,0,a.Width,a.Height);
            var da=a.LockBits(rect,ImageLockMode.ReadOnly,PixelFormat.Format32bppArgb);
            var db=b.LockBits(rect,ImageLockMode.ReadOnly,PixelFormat.Format32bppArgb);
            try {
                var aa=new byte[da.Stride*a.Height];var bb=new byte[db.Stride*b.Height];
                Marshal.Copy(da.Scan0,aa,0,aa.Length);Marshal.Copy(db.Scan0,bb,0,bb.Length);
                long visible=0;
                for(int y=0;y<a.Height;y++) for(int x=0;x<a.Width;x++) {
                    int ia=y*da.Stride+x*4,ib=y*db.Stride+x*4;
                    if(bb[ib+3]==0) continue;
                    visible++;
                    if(bb[ib]!=aa[ia] || bb[ib+1]!=aa[ia+1] || bb[ib+2]!=aa[ia+2])
                        throw new Exception("Changed source pixel at "+x+","+y+": "+mask);
                }
                if(visible==0) throw new Exception("Empty mask: "+mask);
                return visible;
            } finally {a.UnlockBits(da);b.UnlockBits(db);}
        }
    }
}
'@
$root=Split-Path -Parent $PSScriptRoot
$manifest=Get-Content -Encoding UTF8 -Raw -LiteralPath (Join-Path $root 'public/assets/images/scenes/registration.json') | ConvertFrom-Json
$total=0
foreach ($entry in $manifest.PSObject.Properties) {
    $a=Join-Path $root ('public'+$entry.Value.background)
    $b=Join-Path $root ('public'+$entry.Value.image)
    $count=[PixelRegistration]::Check($a,$b)
    $total+=$count
    Write-Output "$($entry.Name): $count source pixels match exactly"
}
Write-Output "Verified $total opaque pixels across $(@($manifest.PSObject.Properties).Count) registered layers."
