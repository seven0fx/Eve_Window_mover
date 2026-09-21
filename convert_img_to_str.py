from PIL import Image
import base64
import io


def save_img_file_to_py_file(input, output):
    with open(input,'rb') as f:
        by = f.read()
        by = base64.b64encode(by)

    with open(output,'w') as f:
        f.write(f"data={by}")


save_img_file_to_py_file('login.jpg','img_data.py')


from img_data import data
neu = Image.open(io.BytesIO(base64.b64decode(data)))
neu.show()
