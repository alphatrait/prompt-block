# parser.py

def blocks(file_path):
    with open(file_path, 'r') as file:
        content = file.read()

    content = content.replace('<positive>', 'this is positive ')
    content = content.replace('</positive>', ' end of this is positive')

    return content
