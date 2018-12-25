#!/bin/bash
basedir="$(cd `dirname $0`; pwd)"
rootdir="$(cd ${basedir}/../.. ; pwd)"

declare -a patterns=(
                     "except\s.*, e.*:"
		     )
declare -a py2_syntax=(
                     "','"
                     )
declare -a py2_3_syntax=(
                     "exception with 'as'"
                     )

for i in "${!patterns[@]}"
do
    bad_file_found=$(grep -Pr -e "${patterns[$i]}" plugins/ src/ *.py | grep -v '#.*\bNOCHECK\b.*' | sed -E 's/([^:]*)(:.*)/\1/' | sort -u | grep '.py$')

    if [ -n "${bad_file_found}" ]
    then
        failed=yes
        echo "** PY2/3 CHECK FAILED ** Please consider using ${py2_3_syntax[$i]}" over ${py2_syntax[$i]}" in file(s):"
        echo "${bad_file_found}"
    fi
done
if [[ -v failed ]]; then exit 1; else exit 0; fi
