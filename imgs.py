from PIL import Image
import requests
from retry import retry
import os, json, math, shutil, base64


first_page_query = """
{   
    user(login: "{user}") {
        followers(last: 100) {
            nodes {
                login
                name
                avatarUrl
                url
            }
            pageInfo {
                startCursor
                hasPreviousPage
            }
        }
    }
}
"""

page_query = """
{
  user(login: "{user}") {
    followers(last: 100, before: "{cursor}") {
      nodes {
        login
        name
        avatarUrl
        url
      }
      pageInfo {
        startCursor
        hasPreviousPage
      }
    }
  }
}
"""


@retry(tries=10, delay=2)
def do_query(token: str, query: str):
    request = requests.post('https://api.github.com/graphql',
                            json={'query': query}, headers={"Authorization": "Bearer " + token})
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception("Query failed to run by returning code of {}. {}: {}".format(
            request.status_code, query, request.content))


def get_followers(token: str, user: str) -> list:
    result = []
    page = do_query(token, first_page_query.replace("{user}", user))
    has_next = page["data"]["user"]["followers"]["pageInfo"]["hasPreviousPage"]
    cursor = page["data"]["user"]["followers"]["pageInfo"]["startCursor"]
    data = page["data"]["user"]["followers"]["nodes"]
    data.reverse()
    result.extend(data)
    print(has_next, cursor)
    while has_next:
        page = do_query(token, page_query.replace(
            "{user}", user).replace("{cursor}", cursor))
        has_next = page["data"]["user"]["followers"]["pageInfo"]["hasPreviousPage"]
        cursor = page["data"]["user"]["followers"]["pageInfo"]["startCursor"]
        data = page["data"]["user"]["followers"]["nodes"]
        data.reverse()
        result.extend(data)
        print(has_next, cursor)
    with open("followers.json",'w') as f:
        json.dump(result, f, indent=4)
    return result


@retry(tries=10, delay=2)
def download(url: str, filename: str):
    img = requests.get(url)
    with open(filename,'wb') as f:
        f.write(img.content)


def download_imgs():
    shutil.rmtree("imgs", ignore_errors=True)
    os.mkdir("imgs")
    with open('followers.json') as f:
        followers = json.load(f)
        print(len(list(followers)))
        for (id,follower) in enumerate(followers):
            print(id, follower)
            download(follower["avatarUrl"], "imgs/{}.png".format(id))


def composite_image(image_size: int):
    images_list = os.listdir("imgs")
    images_list.sort(key=lambda x: int(x[:-4]))
    length = len(images_list)
    each_size = math.ceil(image_size / math.floor(math.sqrt(length)))
    lines = math.ceil(math.sqrt(length))
    rows = math.ceil(math.sqrt(length))
    image = Image.new('RGB', (each_size * lines, each_size * rows))
    row = 0
    line = 0
    for file in images_list:
        try:
            with Image.open("imgs/"+file) as img:
                img = img.resize((each_size, each_size))
                image.paste(img, (line * each_size, row * each_size))
                line += 1
                if line == lines:
                    line = 0
                    row += 1
        except IOError as e:
            print(e)
            continue
    image.save("all.png")


def gen_svg(img_len: int = 24, space: int = 2, num_per_line: int = 20):
    with open('followers.json') as f:
        followers = json.load(f)
        count = len(list(followers))
        lines = math.ceil(count/num_per_line)
        print(lines)
        height = lines*(img_len+space) + space
        width = (img_len+space)*num_per_line + space
        
        with open("all.svg",'w') as svg:
            svg.write("""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}">
                            <style>.p-svg { cursor: pointer; }</style>""".replace("{width}", str(width)).replace("{height}", str(height)))
            for (id,follower) in enumerate(followers):
                x = (id%num_per_line)*(space+img_len) + space
                y = (id//num_per_line)*(space+img_len) + space
                with open('imgs/{}.png'.format(id), "rb") as img:
                    data = base64.b64encode(img.read()).decode('ascii')
                    i = """<a xlink:href="{url}" class="p-svg" target="_blank" id="{loginname}"><image x="{x}" y="{y}" width="{img_len}" height="{img_len}" xlink:href="data:image/png;base64,{data}"/></a>""".format(
                        url = follower["url"],
                        loginname = follower["login"],
                        img_len = str(img_len),
                        x=str(x),
                        y=str(y),
                        data = data
                    )
                    svg.write(i)
            svg.write("</svg>")
        

if __name__ == '__main__':
    token = os.getenv("TOKEN")
    user = os.getenv("USER")
    size = os.getenv("SIZE")
    get_followers(token, user)
    download_imgs()
    gen_svg(128, 0, 34)
    composite_image(int(size))
