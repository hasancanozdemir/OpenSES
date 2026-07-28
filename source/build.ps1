param(
    [ValidateSet('Release', 'Debug', 'All')]
    [string]$Configuration = 'Release',
    [string]$Compiler = 'gfortran',
    [ValidateSet('Auto', 'Make', 'Direct')]
    [string]$BuildEngine = 'Auto',
    [switch]$Clean,
    [switch]$NoStatic,
    [switch]$VerboseBuild
)

$ErrorActionPreference = 'Stop'

function Resolve-CompilerCommand {
    param([string]$Name)

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd
    }

    $candidates = @(
        'C:\msys64\ucrt64\bin\gfortran.exe',
        'C:\msys64\mingw64\bin\gfortran.exe',
        'C:\msys64\clang64\bin\gfortran.exe',
        'C:\mingw64\bin\gfortran.exe',
        'C:\Strawberry\c\bin\gfortran.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return Get-Command $candidate -ErrorAction SilentlyContinue
        }
    }

    throw "Required command '$Name' was not found on PATH and no common local gfortran path was found. Install a GNU Fortran toolchain (for example MSYS2/mingw-w64) and retry, or pass -Compiler with a full path to gfortran.exe."
}

function Resolve-MakeCommand {
    $names = @('make', 'mingw32-make')
    foreach ($name in $names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd
        }
    }

    return $null
}

function Invoke-Checked {
    param(
        [string]$Exe,
        [string[]]$CommandArgs
    )

    if ($VerboseBuild) {
        Write-Host "$Exe $($CommandArgs -join ' ')"
    }

    & $Exe @CommandArgs

    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed with exit code {0}: {1} {2}" -f $LASTEXITCODE, $Exe, ($CommandArgs -join ' '))
    }
}

$srcF95 = @(
    'getver.f95',
    'ancill.f95'
)

$srcFor = @(
    'ACEST2.FOR', 'DTHTS2.FOR', 'FLYWHL.FOR', 'INPUT.FOR', 'LSINS.FOR', 'OMEGA5.FOR', 'PINPNT.FOR', 'RELHUM.FOR', 'SIMQ2.FOR', 'TRINS.FOR',
    'AIR.FOR', 'EERROR.FOR', 'FORCE1.FOR', 'INTEXT.FOR', 'MAXMIN.FOR', 'OMGJ1.FOR', 'PRINT.FOR', 'RESIST.FOR', 'SUMARY.FOR', 'TRSLOP.FOR',
    'ALCHAR.FOR', 'EQUAT.FOR', 'FORCEL.FOR', 'JINS.FOR', 'MMAX.FOR', 'OMGJ2.FOR', 'RKTHRM.FOR', 'THDERV.FOR', 'VSINS.FOR', 'WETBLB.FOR',
    'AMPERE.FOR', 'CHECKI.FOR', 'EXTINT.FOR', 'GARAGE.FOR', 'JULIE.FOR', 'MMIN.FOR', 'OMGJ3.FOR', 'PSI.FOR', 'RSTREAD.FOR', 'THNODE.FOR',
    'BEI.FOR', 'CHECKR.FOR', 'FCTORL.FOR', 'GRID.FOR', 'KEI.FOR', 'OMEGA1.FOR', 'OMGJ4.FOR', 'QDERIV.FOR', 'RSTWRITE.FOR', 'TORQUE.FOR',
    'BER.FOR', 'CREAT2.FOR', 'HEAT.FOR', 'KER.FOR', 'OMEGA2.FOR', 'OMGJ5.FOR', 'QSQLP.FOR', 'SIMERR.FOR', 'TRAIN.FOR', 'WLLTM2.FOR',
    'BESSEL.FOR', 'CREAT3.FOR', 'FINS.FOR', 'HEATUP.FOR', 'LATENT.FOR', 'OMEGA3.FOR', 'OMGJ6.FOR', 'QUARRK.FOR', 'SIMLAT.FOR', 'TRANST.FOR',
    'DSES.FOR', 'FLOWAY.FOR', 'HOOKUP.FOR', 'LOCATE.FOR', 'OMEGA4.FOR', 'RATES.FOR', 'SIMQ1.FOR', 'TRIDG3.FOR', 'FILESUBS.FOR', 'JSONPIT.FOR'
)

function Build-Target {
    param([ValidateSet('Release', 'Debug')][string]$Target)

    $outDir = if ($Target -eq 'Release') { 'release' } else { 'debug' }
    $exeName = 'OpenSES.exe'
    $exePath = Join-Path $outDir $exeName

    New-Item -Path $outDir -ItemType Directory -Force | Out-Null

    $flagsF95 = @('-falign-commons', '-Wno-align-commons', '-pedantic')
    $flagsFor = @('-falign-commons', '-Wno-align-commons', '-std=legacy')

    if ($Target -eq 'Debug') {
        $flagsF95 += '-ggdb'
        $flagsFor += '-ggdb'
    }

    $objects = @()

    foreach ($src in $srcF95) {
        $obj = Join-Path $outDir ([IO.Path]::GetFileNameWithoutExtension($src) + '.o')
        Invoke-Checked -Exe $Compiler -CommandArgs ($flagsF95 + @('-c', $src, '-o', $obj))
        $objects += $obj
    }

    foreach ($src in $srcFor) {
        $obj = Join-Path $outDir ([IO.Path]::GetFileNameWithoutExtension($src) + '.o')
        Invoke-Checked -Exe $Compiler -CommandArgs ($flagsFor + @('-c', $src, '-o', $obj))
        $objects += $obj
    }

    $linkArgs = @('-o', $exePath) + $objects
    if (-not $NoStatic) {
        $linkArgs += '-static'
    }

    Invoke-Checked -Exe $Compiler -CommandArgs $linkArgs

    Write-Host "Built $Target executable: $exePath"
}

function Invoke-MakeBuild {
    param(
        [string]$MakeExe,
        [ValidateSet('Release', 'Debug', 'All')][string]$Target,
        [switch]$DoClean
    )

    if ($DoClean) {
        Invoke-Checked -Exe $MakeExe -CommandArgs @('clean')
    }

    $targetArg = switch ($Target) {
        'Release' { 'release' }
        'Debug' { 'debug' }
        'All' { 'all' }
    }

    Invoke-Checked -Exe $MakeExe -CommandArgs @($targetArg)
    Write-Host "Built using make target: $targetArg"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $scriptDir
try {
    $makeCmd = Resolve-MakeCommand

    if ($BuildEngine -eq 'Make' -and -not $makeCmd) {
        throw "BuildEngine=Make was requested, but neither make nor mingw32-make was found on PATH."
    }

    $useMake = $false
    if ($BuildEngine -eq 'Make') {
        $useMake = $true
    }
    elseif ($BuildEngine -eq 'Auto' -and $makeCmd) {
        $useMake = $true
    }

    if ($useMake) {
        if ($VerboseBuild) {
            Write-Host "Using make-based build path."
        }

        Invoke-MakeBuild -MakeExe $makeCmd.Source -Target $Configuration -DoClean:$Clean
    }
    else {
        if ($VerboseBuild) {
            Write-Host "Using direct gfortran build path."
        }

        $compilerCmd = Resolve-CompilerCommand -Name $Compiler

        # Ensure compiler helper tools (as, ld, frontends) are discoverable.
        $compilerDir = Split-Path -Parent $compilerCmd.Source
        if (-not [string]::IsNullOrWhiteSpace($compilerDir)) {
            $pathEntries = $env:PATH -split ';'
            if ($pathEntries -notcontains $compilerDir) {
                $env:PATH = "$compilerDir;$env:PATH"
            }
        }

        if ($Clean) {
            Remove-Item -Path '.\release\*.o', '.\debug\*.o' -Force -ErrorAction SilentlyContinue
            Remove-Item -Path '.\release\OpenSES.exe', '.\debug\OpenSES.exe' -Force -ErrorAction SilentlyContinue
        }

        switch ($Configuration) {
            'Release' { Build-Target -Target 'Release' }
            'Debug' { Build-Target -Target 'Debug' }
            'All' {
                Build-Target -Target 'Release'
                Build-Target -Target 'Debug'
            }
        }
    }
}
finally {
    Pop-Location
}
