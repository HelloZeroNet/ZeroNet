import re


def prefix(content):
    content = re.sub(
        "@keyframes (.*? {.*?}\s*})", "@keyframes \\1\n@-webkit-keyframes \\1\n@-moz-keyframes \\1\n",
        content, flags=re.DOTALL
    )
    content = re.sub(
        '([^-\*])(border-radius|box-shadow|appearance|transition|animation|box-sizing|' +
        'backface-visibility|transform|filter|perspective|animation-[a-z-]+): (.*?)([;}])',
        '\\1-webkit-\\2: \\3; -moz-\\2: \\3; -o-\\2: \\3; -ms-\\2: \\3; \\2: \\3 \\4', content
    )
    content = re.sub(
        '(?<=[^a-zA-Z0-9-])([a-zA-Z0-9-]+): {0,1}(linear-gradient)\((.*?)(\)[;\n])',
        '\\1: -webkit-\\2(\\3);' +
        '\\1: -moz-\\2(\\3);' +
        '\\1: -o-\\2(\\3);' +
        '\\1: -ms-\\2(\\3);' +
        '\\1: \\2(\\3);', content
    )
    return content

if __name__ == "__main__":
    print prefix("""
    .test {
        border-radius: 5px;
        background: linear-gradient(red, blue);
    }


    @keyframes flip {
      0%   { transform: perspective(120px) rotateX(0deg) rotateY(0deg); }
      50%  { transform: perspective(120px) rotateX(-180.1deg) rotateY(0deg) }
      100% { transform: perspective(120px) rotateX(-180deg) rotateY(-179.9deg); }
    }


    """)
