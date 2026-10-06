#!/usr/bin/env python3

from glob import glob
from pathlib import Path
import os
import itertools
import hashlib
import subprocess
import sys
import re
from datetime import datetime
from string import StringFileConverter
from tm_tutor import TMDataBuilder, TutorDataBuilder

if sys.platform.startswith('win'):
    PathVar = os.environ.get('Path')
    Paths = PathVar.split(';')
    PATH = ''
    for candidatePath in Paths:
        if 'devkitARM' in candidatePath:
            PATH = candidatePath
            break
    if PATH == '':
        print('DevKit does not exist in your Path variable.\nChecking default location.')
        PATH = 'C://devkitPro//devkitARM//bin'
        if os.path.isdir(PATH) is False:
            print('...\nDevkit not found.')
            sys.exit(1)
        else:
            print('Devkit found.')

    PREFIX = '/arm-none-eabi-'
    AS = PATH + PREFIX + 'as'
    CC = PATH + PREFIX + 'gcc'
    LD = PATH + PREFIX + 'ld'
    GR = 'deps/grit.exe'
    WAV2AGB = 'deps/wav2agb.exe'
    MID2AGB = 'deps/mid2agb.exe'
    OBJCOPY = PATH + PREFIX + 'objcopy'

else:  # Linux, OSX, etc.
    PREFIX = 'arm-none-eabi-'
    AS = PREFIX + 'as'
    CC = PREFIX + 'gcc'
    LD = PREFIX + 'ld'
    GR = "grit"
    WAV2AGB = 'wav2agb'
    MID2AGB = 'mid2agb'
    OBJCOPY = PREFIX + 'objcopy'

SRC = './src'
GRAPHICS = './graphics'
ASSEMBLY = './assembly'
STRINGS = './strings'
AUDIO = './audio'
BUILD = './build'
IMAGES = './Images'
ASFLAGS = ['-mthumb', '-I', ASSEMBLY]
LDFLAGS = ['BPRE.ld', '-T', 'linker.ld']
CFLAGS = ['-mthumb', '-mno-thumb-interwork', '-mcpu=arm7tdmi', '-mtune=arm7tdmi',
          '-mno-long-calls', '-march=armv4t', '-Wall', '-Wextra', '-Os', '-fira-loop-pressure', '-fipa-pta']


CANONICAL_U16_ABILITIES = {
    'ABILITY_GORILLATACTICS',
    'ABILITY_NEUTRALIZINGGAS',
    'ABILITY_PASTELVEIL',
    'ABILITY_HUNGERSWITCH',
    'ABILITY_QUICKDRAW',
    'ABILITY_UNSEENFIST',
    'ABILITY_CURIOUSMEDICINE',
    'ABILITY_TRANSISTOR',
    'ABILITY_DRAGONSMAW',
    'ABILITY_CHILLINGNEIGH',
    'ABILITY_GRIMNEIGH',
    'ABILITY_ASONEICERIDER',
    'ABILITY_ASONESHADOWRIDER',
    'ABILITY_LINGERINGAROMA',
    'ABILITY_SEEDSOWER',
    'ABILITY_THERMALEXCHANGE',
    'ABILITY_ANGERSHELL',
    'ABILITY_PURIFYINGSALT',
    'ABILITY_WELLBAKEDBODY',
    'ABILITY_WINDRIDER',
    'ABILITY_GUARDDOG',
    'ABILITY_ROCKYPAYLOAD',
    'ABILITY_WINDPOWER',
    'ABILITY_ZEROTOHERO',
    'ABILITY_COMMANDER',
    'ABILITY_ELECTROMORPHOSIS',
    'ABILITY_PROTOSYNTHESIS',
    'ABILITY_QUARKDRIVE',
    'ABILITY_GOODASGOLD',
    'ABILITY_VESSELOFRUIN',
    'ABILITY_SWORDOFRUIN',
    'ABILITY_TABLETSOFRUIN',
    'ABILITY_BEADSOFRUIN',
    'ABILITY_ORICHALCUMPULSE',
    'ABILITY_HADRONENGINE',
    'ABILITY_OPPORTUNIST',
    'ABILITY_CUDCHEW',
    'ABILITY_SHARPNESS',
    'ABILITY_SUPREMEOVERLORD',
    'ABILITY_COSTAR',
    'ABILITY_TOXICDEBRIS',
    'ABILITY_ARMORTAIL',
    'ABILITY_EARTHEATER',
    'ABILITY_MYCELIUMMIGHT',
    'ABILITY_HOSPITALITY',
    'ABILITY_MINDSEYE',
    'ABILITY_EMBODYASPECTTEALMASK',
    'ABILITY_EMBODYASPECTHEARTHFLAMEMASK',
    'ABILITY_EMBODYASPECTWELLSPRINGMASK',
    'ABILITY_EMBODYASPECTCORNERSTONEMASK',
    'ABILITY_TOXICCHAIN',
    'ABILITY_SUPERSWEETSYRUP',
    'ABILITY_TERASHIFT',
    'ABILITY_TERASHELL',
    'ABILITY_TERAFORMZERO',
    'ABILITY_POISONPUPPETEER',
    'ABILITY_PIERCINGDRILL',
    'ABILITY_DRAGONIZE',
    'ABILITY_313',
    'ABILITY_EELEVATE',
    'ABILITY_314',
    'ABILITY_MEGA_SOL',
    'ABILITY_316',
    'ABILITY_FIRE_MANE',
    'ABILITY_317',
    'ABILITY_SPICY_SPRAY',
}

# Species whose old DPE records used an effect-sharing byte instead of their
# actual ability identity.  These values feed the canonical u16 table only.
SPECIES_ABILITY_OVERRIDES = {
    'SPECIES_GALLADE': ('ABILITY_STEADFAST', 'ABILITY_SHARPNESS', 'ABILITY_JUSTIFIED'),
    'SPECIES_KLEAVOR': ('ABILITY_SWARM', 'ABILITY_SHEERFORCE', 'ABILITY_SHARPNESS'),
    'SPECIES_KLAWF': ('ABILITY_ANGERSHELL', 'ABILITY_SHELLARMOR', 'ABILITY_REGENERATOR'),
    'SPECIES_ESPATHRA': ('ABILITY_OPPORTUNIST', 'ABILITY_FRISK', 'ABILITY_SPEEDBOOST'),
    'SPECIES_FLAMIGO': ('ABILITY_SCRAPPY', 'ABILITY_TANGLEDFEET', 'ABILITY_COSTAR'),
    'SPECIES_VELUZA': ('ABILITY_MOLDBREAKER', 'ABILITY_NONE', 'ABILITY_SHARPNESS'),
    'SPECIES_FARIGIRAF': ('ABILITY_CUDCHEW', 'ABILITY_ARMORTAIL', 'ABILITY_SAPSIPPER'),
    'SPECIES_WALKING_WAKE': ('ABILITY_PROTOSYNTHESIS', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_TREADS': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_BUNDLE': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_HANDS': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_JUGULIS': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_MOTH': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_THORNS': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_VALIANT': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_LEAVES': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_WO_CHIEN': ('ABILITY_TABLETSOFRUIN', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_CHIEN_PAO': ('ABILITY_SWORDOFRUIN', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_TING_LU': ('ABILITY_VESSELOFRUIN', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_CHI_YU': ('ABILITY_BEADSOFRUIN', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_URSALUNA_BLOODMOON': ('ABILITY_MINDSEYE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_HYDRAPPLE': ('ABILITY_SUPERSWEETSYRUP', 'ABILITY_REGENERATOR', 'ABILITY_STICKYHOLD'),
    'SPECIES_GOUGING_FIRE': ('ABILITY_PROTOSYNTHESIS', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_RAGING_BOLT': ('ABILITY_PROTOSYNTHESIS', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_BOULDER': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_IRON_CROWN': ('ABILITY_QUARKDRIVE', 'ABILITY_NONE', 'ABILITY_NONE'),
    'SPECIES_TERAPAGOS_TERASTAL': ('ABILITY_TERASHELL', 'ABILITY_NONE', 'ABILITY_NONE'),
}


def GenerateAbilityTables():
    source_path = os.path.join(SRC, 'Base_Stats.c')
    generated_dir = os.path.join(SRC, 'generated')
    os.makedirs(generated_dir, exist_ok=True)
    with open(source_path, encoding='utf-8', errors='replace') as source_file:
        source = source_file.read()

    ability_fields = re.compile(r'(\.(?:ability1|ability2|hiddenAbility)\s*=\s*)(ABILITY_[A-Z0-9_]+)')
    compat_source = ability_fields.sub(
        lambda m: m.group(1) + 'ABILITY_NONE' if m.group(2) in CANONICAL_U16_ABILITIES else m.group(0),
        source)
    compat_source = compat_source.replace('#include "defines.h"', '#include "../defines.h"')
    compat_source = compat_source.replace('#include "../include/', '#include "../../include/')
    with open(os.path.join(generated_dir, 'Base_Stats_Compat.c'), 'w', encoding='utf-8', newline='\n') as output:
        output.write(compat_source)

    entries = []
    current_species = None
    current = {'ability1': 'ABILITY_NONE', 'ability2': 'ABILITY_NONE', 'hiddenAbility': 'ABILITY_NONE'}
    for line in source.splitlines():
        species_match = re.match(r'\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=', line)
        if species_match:
            if current_species is not None:
                entries.append((current_species, current.copy()))
            current_species = species_match.group(1)
            current = {'ability1': 'ABILITY_NONE', 'ability2': 'ABILITY_NONE', 'hiddenAbility': 'ABILITY_NONE'}
        field_match = re.search(r'\.(ability1|ability2|hiddenAbility)\s*=\s*(ABILITY_[A-Z0-9_]+)', line)
        if current_species is not None and field_match:
            current[field_match.group(1)] = field_match.group(2)
    if current_species is not None:
        entries.append((current_species, current))

    entries = [(species, dict(zip(('ability1', 'ability2', 'hiddenAbility'), SPECIES_ABILITY_OVERRIDES[species])))
               if species in SPECIES_ABILITY_OVERRIDES else (species, abilities)
               for species, abilities in entries]

    with open(os.path.join(generated_dir, 'Species_Abilities.c'), 'w', encoding='utf-8', newline='\n') as output:
        output.write('#include "../defines.h"\n#include "../../include/abilities.h"\n#include "../../include/base_stats.h"\n\n')
        output.write('const struct SpeciesAbilities gSpeciesAbilities[] =\n{\n')
        for species, abilities in entries:
            output.write('    [%s] = {%s, %s, %s},\n' % (species, abilities['ability1'], abilities['ability2'], abilities['hiddenAbility']))
        output.write('};\n')


class Master:
    @staticmethod
    def init():
        Master.printedCompilingImages = False
        Master.printedCompilingAudio = False
        Master.printedCompilingMusic = False

    @staticmethod
    def printCompilingImages():
        if not Master.printedCompilingImages:
            # Used to tell the script whether or not the string 'Compiling Images' has been printed
            Master.printedCompilingImages = True
            print('Compiling Images')

    @staticmethod
    def printCompilingAudio():
        if not Master.printedCompilingAudio:
            # Used to tell the script whether or not the string 'Compiling Audio' has been printed
            Master.printedCompilingAudio = True
            print('Compiling Audio')

    @staticmethod
    def printCompilingMusic():
        if not Master.printedCompilingMusic:
            # Used to tell the script whether or not the string 'Compiling Music' has been printed
            Master.printedCompilingMusic = True
            print('Compiling Music')


def RunCommand(cmd: [str]):
    """Runs the command line command."""
    try:
        subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        try:
            print(e.output.decode(), file=sys.stderr)
        except:
            print(e)
        sys.exit(1)


def CreateOutputFile(fileName: str, newFileName: str) -> [str, bool]:
    """Helper function to produce object file output."""
    if not os.path.isfile(fileName):
        return [newFileName, False]

    fileExists = os.path.isfile(newFileName)

    # If the object file was created after the file was last modified
    if fileExists and os.path.getmtime(newFileName) > os.path.getmtime(fileName):
        return [newFileName, False]

    return [newFileName, True]


def MakeGeneralOutputFile(fileName: str) -> [str, bool]:
    """Return hash of filename to use as object filename."""
    m = hashlib.md5()
    m.update(fileName.encode())
    newFileName = os.path.join(BUILD, m.hexdigest() + '.o')

    return CreateOutputFile(fileName, newFileName)


def MakeOutputImageFile(assemblyFile: str) -> [str, bool]:
    """Return 'IMG_' + hash of filename to use as object filename."""
    m = hashlib.md5()
    m.update(assemblyFile.encode())
    objectFile = os.path.join(BUILD, 'IMG_' + m.hexdigest() + '.o')

    return CreateOutputFile(assemblyFile, objectFile)


def MakeOutputAudioFile(assemblyFile: str) -> [str, bool]:
    """Return "SND_" + hash of filename to use as object filename."""
    objectFile = os.path.join(BUILD, 'SND_' + assemblyFile.split("gCry")[1].split(".s")[0] + '.o')
    return CreateOutputFile(assemblyFile, objectFile)


def MakeOutputMusicFile(assemblyFile: str) -> [str, bool]:
    """Return "MUS_" + hash of filename to use as object filename."""
    if sys.platform.startswith('win'):  # Windows
        objectFile = os.path.join(BUILD, 'MUS_'
                                  + assemblyFile.split('\\')[len(assemblyFile.split('\\')) - 1].split(".s")[0] + '.o')
    else:  # Linux, OSX, etc.
        objectFile = os.path.join(BUILD, 'MUS_'
                                  + assemblyFile.split('/')[len(assemblyFile.split('/')) - 1].split(".s")[0] + '.o')

    return CreateOutputFile(assemblyFile, objectFile)


def DoMiddleManAssembly(originalFile: str, assemblyFile: str, flagFile: str, flags: [str],
                        cmd: [str], func, printingFunc, isMusic: bool) -> str:
    """Process assembly files generated by things like grit, wav2agb, or mid2agb."""
    objectFile = func(assemblyFile)[0]
    fileExists = os.path.isfile(objectFile)
    flagFileExists = os.path.isfile(flagFile)

    if fileExists \
            and os.path.getmtime(objectFile) > os.path.getmtime(originalFile) \
            and (not flagFileExists or os.path.getmtime(objectFile) > os.path.getmtime(flagFile)):
        # If the .o file was created after the original and flag file were last modified
        return objectFile
    else:  # The original file or the flag file were modified recently
        printingFunc()
        RunCommand(cmd)

    if isMusic:  # Try to update the voicegroup manually
        counter = 0
        lineToChange = ''
        with open(assemblyFile, 'r') as file:
            for line in file:
                counter += 1
                if '_grp,' in line:
                    lineToChange = line.split('voicegroup')[0]
                    break

        if flags != [] and lineToChange != '' and '-G' in flags:
            ChangeFileLine(assemblyFile, counter, lineToChange + flags[flags.index('-G') + 1] + '\n')

    regenerateObjectFile = func(assemblyFile)[1]
    if regenerateObjectFile is False:
        os.remove(assemblyFile)
        return objectFile  # No point in recompiling file

    cmd = [AS] + ASFLAGS + ['-c', assemblyFile, '-o', objectFile]
    RunCommand(cmd)
    os.remove(assemblyFile)
    return objectFile


def ProcessAssembly(assemblyFile: str) -> str:
    """Assemble."""
    objectFile, regenerateObjectFile = MakeGeneralOutputFile(assemblyFile)
    if regenerateObjectFile is False:
        return objectFile  # No point in recompiling file

    try:
        print('Assembling %s' % assemblyFile)
        cmd = [AS] + ASFLAGS + ['-c', assemblyFile, '-o', objectFile]
        RunCommand(cmd)

    except FileNotFoundError:
        print('Error! The assembler could not be located.\n'
              + 'Are you sure you set up your path to devkitPro/devkitARM/bin correctly?')
        sys.exit(1)

    return objectFile


def ProcessC(cFile: str) -> str:
    """Compile C."""
    objectFile, regenerateObjectFile = MakeGeneralOutputFile(cFile)
    if regenerateObjectFile is False:
        return objectFile  # No point in recompiling file

    try:
        print('Compiling %s' % cFile)
        cmd = [CC] + CFLAGS + ['-c', cFile, '-o', objectFile]
        RunCommand(cmd)

    except FileNotFoundError:
        print('Error! The C compiler could not be located.\n'
              + 'Are you sure you set up your path to devkitPro/devkitARM/bin correctly?')
        sys.exit(1)

    return objectFile


def ProcessString(stringFile: str) -> str:
    """Build and assemble strings."""
    assemblyFile = stringFile.split('.string')[0] + '.s'
    objectFile = MakeGeneralOutputFile(assemblyFile)[0]
    fileExists = os.path.isfile(objectFile)

    if fileExists and os.path.getmtime(objectFile) > os.path.getmtime(stringFile):
        # If the .o file was created after the string file was last modified
        return objectFile

    print('Building Strings %s' % stringFile)
    StringFileConverter(stringFile)

    cmd = [AS] + ASFLAGS + ['-c', assemblyFile, '-o', objectFile]
    RunCommand(cmd)
    os.remove(assemblyFile)
    return objectFile


def GetFlagsFromFlagFile(filePath: str) -> [str]:
    try:
        with open(filePath, "r") as file:
            line = file.readline()  # Only needs the first line
            flags = line.split()
    except FileNotFoundError:
        print('"{}" could not be found.'.format(filePath))
        sys.exit(1)

    return flags


def ProcessSpriteSet(fileListing: [str], flags: [str], outputFile: str, title: str):
    assembledFile = os.path.join(ASSEMBLY, 'generated', outputFile)
    if (not os.path.isfile(assembledFile)
            or os.path.getsize(assembledFile) <= len('@THIS IS A GENERATED FILE! DO NOT MODIFY IT!\n')
            or max(list(map(os.path.getmtime, fileListing))) > os.path.getmtime(assembledFile)):  # If a sprite has been modified
        print("Processing {}.".format(title))
        temporaryFile = assembledFile + '.tmp'
        try:
            with open(temporaryFile, 'w') as combinedFile:
                combinedFile.write('@THIS IS A GENERATED FILE! DO NOT MODIFY IT!\n')
                for sprite in fileListing:
                    assembled = sprite.split('.png')[0] + '.s'

                    if (not os.path.isfile(assembled)
                            or os.path.getmtime(sprite) > os.path.getmtime(assembled)):
                        RunCommand([GR, sprite] + flags + ['-o', assembled])

                    with open(assembled, 'r') as tempFile:
                        combinedFile.write(tempFile.read())
            os.replace(temporaryFile, assembledFile)
        finally:
            if os.path.isfile(temporaryFile):
                os.remove(temporaryFile)


def ProcessSpriteGraphics():
    frontFlags = GetFlagsFromFlagFile(GRAPHICS + "/frontspriteflags.grit")
    backFlags = GetFlagsFromFlagFile(GRAPHICS + "/backspriteflags.grit")
    iconFlags = GetFlagsFromFlagFile(GRAPHICS + "/iconspriteflags.grit")
    castformFlags = GetFlagsFromFlagFile(GRAPHICS + "/castform/gritflags.txt")

    backsprites = [file for file in glob(GRAPHICS + "/backspr" + "**/*.png", recursive=True)]
    frontsprites = [file for file in glob(GRAPHICS + "/frontspr" + "**/*.png", recursive=True)]
    iconsprites = [file for file in glob(GRAPHICS + "/pokeicon" + "**/*.png", recursive=True)]
    castformsprites = [file for file in glob(GRAPHICS + "/castform" + "**/*.png", recursive=True)]

    ProcessSpriteSet(frontsprites, frontFlags, 'frontsprites.s', "Front Sprites")
    ProcessSpriteSet(backsprites, backFlags, 'backsprites.s', "Back Sprites")
    ProcessSpriteSet(iconsprites, iconFlags, 'iconsprites.s', "Icon Sprites")
    ProcessSpriteSet(castformsprites, castformFlags, 'castformsprites.s', "Castform Sprites")


def ProcessAudio(audioFile: str) -> str:
    """Compile audio."""
    assemblyFile = audioFile.split('.wav')[0] + '.s'

    flags = []
    flagFile = audioFile.split('.wav')[0] + '_flags.txt'

    try:
        with open(flagFile, 'r') as file:
            line = file.readline()  # Only needs the first line
            flags = line.strip().split()
    except FileNotFoundError:
        pass

    cmd = [WAV2AGB, audioFile, assemblyFile] + flags

    return DoMiddleManAssembly(audioFile, assemblyFile, flagFile, flags, cmd,
                               MakeOutputAudioFile, Master.printCompilingAudio, False)


def ProcessMusic(midiFile: str) -> str:
    """Compile audio."""
    assemblyFile = midiFile.split('.mid')[0] + '.s'

    flags = []
    flagFile = midiFile.split('.mid')[0] + '_flags.txt'

    try:
        with open(flagFile, 'r') as file:
            line = file.readline()  # Only needs the first line
            flags = line.strip().split()
    except FileNotFoundError:
        pass

    cmd = [MID2AGB, midiFile, assemblyFile] + flags

    return DoMiddleManAssembly(midiFile, assemblyFile, flagFile, flags, cmd,
                               MakeOutputMusicFile, Master.printCompilingMusic, True)


def LinkObjects(objects: itertools.chain) -> str:
    """Link objects into one binary."""
    linked = 'build/linked.o'
    cmd = [LD] + LDFLAGS + ['-o', linked] + list(objects)
    RunCommand(cmd)
    return linked


def Objcopy(binary: str):
    """Run the objcopy."""
    cmd = [OBJCOPY, '-O', 'binary', binary, 'build/output.bin']
    RunCommand(cmd)


def RunGlob(globString: str, fn) -> map:
    """Glob recursively and run the processor function on each file in result."""
    if globString == '**/*.png' or globString == '**/*.bmp':  # Search the GRAPHICS location
        directory = GRAPHICS
    elif globString == '**/*.s':
        directory = ASSEMBLY
    elif globString == '**/*.string':
        directory = STRINGS
    elif globString == '**/*.wav' or globString == '**/*.mid':
        directory = AUDIO
    else:
        directory = SRC

    if sys.version_info > (3, 4):
        try:
            files = glob(os.path.join(directory, globString), recursive=True)
            if globString == '**/*.c':
                files = [file for file in files
                         if os.path.normpath(file) != os.path.normpath(os.path.join(SRC, 'Base_Stats.c'))]
            return map(fn, files)

        except TypeError:
            print('Error compiling. Please make sure Python has been updated to the latest version.')
            sys.exit(1)
    else:
        files = Path(directory).glob(globString)
        return map(fn, map(str, files))


def main():
    Master.init()
    startTime = datetime.now()
    globs = {
        '**/*.s': ProcessAssembly,
        '**/*.c': ProcessC,
        '**/*.string': ProcessString,
        # '**/*.png': ProcessImage,
        # '**/*.bmp': ProcessImage,
        '**/*.wav': ProcessAudio,
        '**/*.mid': ProcessMusic,
    }

    if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
        print("Warning! Python 3.8 may not be able to build this engine.\nPlease downgrade to Python 3.7.4")

    # Create output directory
    try:
        os.makedirs(BUILD)
    except FileExistsError:
        pass

    try:
        try:
            os.makedirs(ASSEMBLY + "/generated")
        except FileExistsError:
            pass

        ProcessSpriteGraphics()
        GenerateAbilityTables()
        TMDataBuilder()
        TutorDataBuilder()

        # Gather source files and process them
        objects = itertools.starmap(RunGlob, globs.items())

        # Link and extract raw binary
        linked = LinkObjects(itertools.chain.from_iterable(objects))
        Objcopy(linked)

    except Exception as e:
        print("There was an error compiling the engine: {}".format(e))
        sys.exit(1)

    # Build special_inserts.asm
    if os.path.isfile('special_inserts.asm'):
        if not os.path.isfile('build/special_inserts.bin') \
                or os.path.getmtime('build/special_inserts.bin') < os.path.getmtime('special_inserts.asm'):
            print('Assembling special_inserts.asm')
            cmd = [AS] + ASFLAGS + ['-c', 'special_inserts.asm', '-o', 'build/special_inserts.o']
            RunCommand(cmd)

            cmd = [OBJCOPY, '-O', 'binary', 'build/special_inserts.o', 'build/special_inserts.bin']
            RunCommand(cmd)

    print('Built in ' + str(datetime.now() - startTime) + '.')


if __name__ == '__main__':
    main()
