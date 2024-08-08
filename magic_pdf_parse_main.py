import os
import json
import copy
from loguru import logger
from magic_pdf.pipe.UNIPipe import UNIPipe
from magic_pdf.pipe.OCRPipe import OCRPipe
from magic_pdf.pipe.TXTPipe import TXTPipe
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
import magic_pdf.model as model_config

model_config.__use_inside_model__ = True

class PDFParser:
    def __init__(self):
        self.pipe = None

    def initialize_pipe(self, pdf_bytes, model_json, image_writer, parse_method):
        if parse_method == "auto":
            jso_useful_key = {"_pdf_type": "", "model_list": model_json}
            self.pipe = UNIPipe(pdf_bytes, jso_useful_key, image_writer)
        elif parse_method == "txt":
            self.pipe = TXTPipe(pdf_bytes, model_json, image_writer)
        elif parse_method == "ocr":
            self.pipe = OCRPipe(pdf_bytes, model_json, image_writer)
        else:
            logger.error("unknown parse method, only auto, ocr, txt allowed")
            exit(1)
    
    def parse_pdf(self, pdf_path, parse_method='auto', model_json_path=None, is_json_md_dump=True, output_dir=None):
        try:
            pdf_name = os.path.basename(pdf_path).split(".")[0]
            pdf_path_parent = os.path.dirname(pdf_path)

            if output_dir:
                output_path = os.path.join(output_dir, pdf_name)
            else:
                output_path = os.path.join(pdf_path_parent, pdf_name)

            output_image_path = os.path.join(output_path, 'images')

            image_path_parent = os.path.basename(output_image_path)
            pdf_bytes = open(pdf_path, "rb").read()

            if model_json_path:
                model_json = json.loads(open(model_json_path, "r", encoding="utf-8").read())
            else:
                model_json = []

            image_writer, md_writer = DiskReaderWriter(output_image_path), DiskReaderWriter(output_path)

            if self.pipe is None:
                self.initialize_pipe(pdf_bytes, model_json, image_writer, parse_method)

            self.pipe.pipe_classify()

            if not model_json:
                if model_config.__use_inside_model__:
                    self.pipe.pipe_analyze()
                else:
                    logger.error("need model list input")
                    exit(1)

            self.pipe.pipe_parse()

            content_list = self.pipe.pipe_mk_uni_format(image_path_parent, drop_mode="none")
            md_content = self.pipe.pipe_mk_markdown(image_path_parent, drop_mode="none")

            if is_json_md_dump:
                json_md_dump(self.pipe, md_writer, pdf_name, content_list, md_content)

        except Exception as e:
            logger.exception(e)

def json_md_dump(pipe, md_writer, pdf_name, content_list, md_content):
    orig_model_list = copy.deepcopy(pipe.model_list)
    md_writer.write(
        content=json.dumps(orig_model_list, ensure_ascii=False, indent=4),
        path=f"{pdf_name}_model.json"
    )

    md_writer.write(
        content=json.dumps(pipe.pdf_mid_data, ensure_ascii=False, indent=4),
        path=f"{pdf_name}_middle.json"
    )

    md_writer.write(
        content=json.dumps(content_list, ensure_ascii=False, indent=4),
        path=f"{pdf_name}_content_list.json"
    )

    md_writer.write(
        content=md_content,
        path=f"{pdf_name}.md"
    )

# 测试
if __name__ == '__main__':
    pdf_path = r"/Users/wuguanlin/wgl/MinerU/demo/first_page.pdf"
    parser = PDFParser()
    parser.parse_pdf(pdf_path)
