#!/bin/sh

set -eu

REPOSITORY="truong51972/coding-kit"
DEFAULT_REF="main"

usage() {
    cat <<'EOF'
Usage: install.sh [--ref BRANCH_OR_TAG] [--all | --list | SKILL...]

Download the selected repository ref, discover its skills, and install them to
${AGENTS_HOME:-$HOME/.agents}/skills.

Options:
  --all              Install every discovered skill.
  --list             List discovered skill names without installing them.
  --ref REF          Use a branch or tag instead of main.
  -h, --help         Show this help.

With no selection, an interactive multi-select menu is opened on /dev/tty.

Examples:
  install.sh --all
  install.sh celery-worker context-management
  install.sh --ref develop --all
  install.sh --list
EOF
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

valid_ref() {
    case "$1" in
        ''|-*|*'..'*|*'//'*|/*|*/|*[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._/-]*) return 1 ;;
        *) return 0 ;;
    esac
}

valid_skill_name() {
    case "$1" in
        ''|-*|*[!abcdefghijklmnopqrstuvwxyz0123456789-]*|*--*|*-) return 1 ;;
        *) return 0 ;;
    esac
}

ref=$DEFAULT_REF
mode=interactive
requested=''

while [ "$#" -gt 0 ]; do
    case "$1" in
        --ref)
            [ "$#" -ge 2 ] || die "--ref requires a branch or tag"
            ref=$2
            shift 2
            ;;
        --all)
            [ "$mode" = interactive ] || die "--all cannot be combined with another selection mode"
            mode=all
            shift
            ;;
        --list)
            [ "$mode" = interactive ] || die "--list cannot be combined with another selection mode"
            mode=list
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*) die "unknown option: $1" ;;
        *)
            [ "$mode" != all ] && [ "$mode" != list ] || die "skill names cannot be combined with --$mode"
            mode=named
            valid_skill_name "$1" || die "invalid skill name: $1"
            requested="${requested}${requested:+
}$1"
            shift
            ;;
    esac
done

while [ "$#" -gt 0 ]; do
    [ "$mode" != all ] && [ "$mode" != list ] || die "skill names cannot be combined with --$mode"
    mode=named
    valid_skill_name "$1" || die "invalid skill name: $1"
    requested="${requested}${requested:+
}$1"
    shift
done

valid_ref "$ref" || die "invalid ref: $ref"

for required_command in curl tar mktemp sort; do
    command -v "$required_command" >/dev/null 2>&1 || die "required command not found: $required_command"
done

tmp=$(mktemp -d "${TMPDIR:-/tmp}/skills-install.XXXXXXXX") || die "could not create temporary directory"
trap 'rm -rf "$tmp"' EXIT
trap 'exit 1' HUP INT TERM

archive=$tmp/repository.tar.gz
url="https://codeload.github.com/$REPOSITORY/tar.gz/$ref"
printf 'Downloading %s at ref %s...\n' "$REPOSITORY" "$ref" >&2
curl -fsSL "$url" -o "$archive" || die "failed to download ref '$ref'"

members=$tmp/archive-members
tar -tzf "$archive" >"$members" 2>/dev/null || die "downloaded archive is not a valid gzip tar archive"
[ -s "$members" ] || die "downloaded archive is empty"

awk '
    /^\// { exit 1 }
    {
        count = split($0, parts, "/")
        if (parts[1] == "" || parts[1] == "." || parts[1] == "..") exit 1
        for (i = 2; i <= count; i++) if (parts[i] == "..") exit 1
        if (root == "") root = parts[1]
        if (parts[1] != root) exit 1
    }
' "$members" || die "archive has an unsafe or malformed layout"

archive_root=$(awk -F/ 'NR == 1 { print $1 }' "$members")
[ -n "$archive_root" ] || die "could not determine archive root"
tar -xzf "$archive" -C "$tmp" 2>/dev/null || die "failed to extract downloaded archive"
skills_root=$tmp/$archive_root/skills
[ -d "$skills_root" ] || die "archive does not contain a skills directory"

discovered=$tmp/discovered
: >"$discovered"
for skill_file in "$skills_root"/*/SKILL.md; do
    [ -f "$skill_file" ] || continue
    skill_dir=${skill_file%/SKILL.md}
    skill_name=${skill_dir##*/}
    valid_skill_name "$skill_name" || die "archive contains an invalid skill directory name: $skill_name"
    printf '%s\n' "$skill_name" >>"$discovered"
done
sort -u "$discovered" -o "$discovered"
[ -s "$discovered" ] || die "archive contains no valid skills/*/SKILL.md entries"

if [ "$mode" = list ]; then
    cat "$discovered"
    exit 0
fi

selected=$tmp/selected
: >"$selected"

if [ "$mode" = all ]; then
    cp "$discovered" "$selected"
elif [ "$mode" = named ]; then
    printf '%s\n' "$requested" | sort -u >"$selected"
else
    if (exec 3<>/dev/tty) 2>/dev/null; then
        exec 3<>/dev/tty
        printf '\nAvailable skills at ref %s:\n' "$ref" >&3
        number=1
        while IFS= read -r skill_name; do
            printf '  %s) %s\n' "$number" "$skill_name" >&3
            number=$((number + 1))
        done <"$discovered"
        printf 'Select skills by number or name (space-separated), or "all": ' >&3
        IFS= read -r choices <&3 || die "could not read selection from /dev/tty"
        exec 3>&-
        [ -n "$choices" ] || die "no skills selected"
        if [ "$choices" = all ]; then
            cp "$discovered" "$selected"
        else
            for choice in $choices; do
                case "$choice" in
                    *[!0123456789]*|'') skill_name=$choice ;;
                    *) skill_name=$(sed -n "${choice}p" "$discovered") ;;
                esac
                [ -n "$skill_name" ] || die "invalid menu selection: $choice"
                valid_skill_name "$skill_name" || die "invalid skill selection: $choice"
                printf '%s\n' "$skill_name" >>"$selected"
            done
            sort -u "$selected" -o "$selected"
        fi
    else
        usage >&2
        die "no TTY is available; pass --all or one or more skill names"
    fi
fi

while IFS= read -r skill_name; do
    if ! grep -F -x "$skill_name" "$discovered" >/dev/null 2>&1; then
        die "unknown skill '$skill_name' at ref '$ref' (use --list to see available skills)"
    fi
done <"$selected"

stage=$tmp/staged
mkdir "$stage"
while IFS= read -r skill_name; do
    source_dir=$skills_root/$skill_name
    [ -d "$source_dir" ] || die "skill directory is missing: $skill_name"
    [ -f "$source_dir/SKILL.md" ] || die "skill is missing SKILL.md: $skill_name"
    cp -R "$source_dir" "$stage/$skill_name" || die "failed to stage skill: $skill_name"
    [ -f "$stage/$skill_name/SKILL.md" ] || die "staged skill is missing SKILL.md: $skill_name"
done <"$selected"

agents_home=${AGENTS_HOME:-${HOME:?HOME is not set}/.agents}
destination=$agents_home/skills
mkdir -p "$destination" || die "could not create destination: $destination"

installed=0
while IFS= read -r skill_name; do
    target=$destination/$skill_name
    incoming=$destination/.${skill_name}.install.$$
    backup=$destination/.${skill_name}.backup.$$
    [ ! -e "$incoming" ] && [ ! -e "$backup" ] || die "temporary install path already exists for $skill_name"

    cp -R "$stage/$skill_name" "$incoming" || die "failed to prepare installation for $skill_name"
    if [ -e "$target" ] || [ -L "$target" ]; then
        mv "$target" "$backup" || die "failed to preserve installed skill: $skill_name"
    fi
    if mv "$incoming" "$target"; then
        rm -rf "$backup"
    else
        rm -rf "$incoming"
        if [ -e "$backup" ] || [ -L "$backup" ]; then
            mv "$backup" "$target" || true
        fi
        die "failed to install skill: $skill_name"
    fi
    installed=$((installed + 1))
    printf 'Installed %s -> %s\n' "$skill_name" "$target"
done <"$selected"

printf 'Done: installed %s skill(s) from ref %s into %s.\n' "$installed" "$ref" "$destination"
