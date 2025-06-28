from langchain_community.document_loaders import DirectoryLoader, TextLoader

DRIVE_FOLDER = "gsma_specs"
loader = DirectoryLoader(DRIVE_FOLDER, glob='**/*.json', show_progress=True, loader_cls=TextLoader)

documents = loader.load()

all_specs = []

for doc in documents:
    all_specs.append(doc.page_content)