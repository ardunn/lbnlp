import os
import tensorflow as tf
from sequence_tagging.model.ner_tf_serving_model import NERServingModel
from sequence_tagging.model.ner_model import NERModel
from sequence_tagging.model.config import Config
from matscholar.process import MatScholarProcess
from matscholar_core.nlp.normalize import Normalizer
import warnings

warnings.filterwarnings("ignore")


class NERClassifier(object):
    """
    A class for sequence tagging with named entity recognition.
    """

    def __init__(self):
        """
        Constructor method for NERClassifier.
        """

        # Configure
        self.config = Configure()
        self.config.dim_word = 250
        self.config.dim_char = 50

        # Check to see if we have a tf serving api running the model
        self.api_url = os.environ.get('TF_SERVING_URL')
        # Load the model
        tf.reset_default_graph()
        if self.api_url is not None:
            self.model = NERServingModel(self.config, api_url=self.api_url)
        else:
            # Make a local NER model if we don't have a remote server (This is significantly slower)
            self.model = NERModel(self.config)
            self.model.build()
            self.model.restore_session(self.config.dir_final_model)
        # Load the normalizer/processor
        self.normalizer = Normalizer()
        self.processor = MatScholarProcess()

    def tag_sequence(self, sequence):
        """
        Use trained NER model to make a prediction on a sequence.

        :param sequence: list; a tokenized sentence
        :return: list of tuples; tagged sentence in (word, iob) format
        """

        tags = self.model.predict(sequence)
        return [(token, tag) for token, tag in zip(sequence, tags)]

    def tag_doc(self, doc):
        """
        Use trained NER model to make predictions for a document.

        Args:
            doc: (str) A document.

        Returns:
            List of tuples containing the tokens and tags from the doc.

        """

        processed_sents, processed_sents_num = self._preprocess(doc)
        tagged_doc = []
        for sent, sent_num in zip(processed_sents, processed_sents_num):
            tags = self.model.predict(sent)
            tagged_doc.append([(token, tag) if token != '<nUm>' else (token_num, tag)
                               for token, token_num, tag in zip(sent, sent_num, tags)])

        return tagged_doc

    def concatenate_entities(self, tagged_doc):
        """
        Concatenates the entities in a tagged document.

        Args:
            tagged_doc: (list of tuple) A list of tagged tokens.

        Returns:
            A list of tagged tokens concatenated by tag type.
        """

        return self.normalizer._concatenate_ents(tagged_doc)

    # TODO: change normalizer.normalize and rewrite this function for that change.
    def normalize_entities(self, doc, tagged_doc):
        """
        Swaps all Matscholar entities in a tagged document with their normalized
        forms.

        Args:
            tagged_doc: (list of tuple) A list of tagged tokens.

        Returns:
            A list of tagged tokens which have been normalized by entity.

        """

        return self.normalizer.normalize([doc], [tagged_doc])[0]  # UGLY!

    def tag_docs(self, docs):
        """
        Use trained NER model to make predictions for a list of documents.

        :param docs: list; a list of documents represented as strings
        :return: list; tagged documents
        """

        tagged_docs = []
        for doc in docs:
            processed_sents, processed_sents_num = self._preprocess(doc)
            tagged_doc = []
            for sent, sent_num in zip(processed_sents, processed_sents_num):
                tags = self.model.predict(sent)
                tagged_doc.append([(token, tag) if token != '<nUm>' else (token_num, tag)
                                   for token, token_num, tag in zip(sent, sent_num, tags)])
            tagged_docs.append(tagged_doc)

        return tagged_docs

    def as_iob(self, docs):
        """
        Tag documents and return in IOB format.

        :param docs: list; a list of documents represented as strings
        :return: list; documents in IOB format
        """
        return self.tag_docs(docs)

    def as_concatenated(self, docs):
        """
        Tags the documents, and concatenates each entity into a single string.

        :param docs: list; a list of documents represented as strings
        :return: list; a list of tagged documents with concatenated entities
        """

        tagged_docs = self.tag_docs(docs)
        concatenated = []
        for doc in tagged_docs:
            conc = self.normalizer._concatenate_ents(doc)
            concatenated.append(conc)
        return concatenated

    def as_normalized(self, docs):
        """
        Tags the documents; each entity is concatenated into a single string, and normalized to
        a canonical form.

        :param docs: list; a list of documents; each document is a list of sentences;
        each sentence is a list of words (tokens)
        :return: list; a list of documents with normalized entities
        """
        tagged_docs = self.tag_docs(docs)
        return self.normalizer.normalize(docs, tagged_docs)

    def _preprocess(self, text):
        """
        Performs preprocessing (tokemnization, lowering etc.)

        :param text: string; document as raw text
        :return: tuple; (processed_sents, processed_sents_num)
        """

        sents = self.processor.tokenize(text)
        processed_sents = []
        processed_sents_num = []
        for sent in sents:
            processed, _ = self.processor.process(sent)
            processed_num, _ = self.processor.process(sent, convert_num=False)
            processed_sents.append(processed)
            processed_sents_num.append(processed_num)
        return processed_sents, processed_sents_num

    def save_model(self, save_dir):
        self.model.build()
        self.model.restore_session(self.config.dir_final_model)
        self.model.save_prediction_model(save_dir)

    def close_session(self):
        self.model.close_session()


class Configure(Config):
    """
    Configuration class for NER model.
    """

    LOCAL_DIR = os.path.dirname(__file__)

    def __init__(self):
        """
        Constructor method for Configure.
        """

        # Path to model data
        self.dir_data = os.path.join(self.LOCAL_DIR, "models/ner")

        # Model saving/loading
        self.dir_final_model = os.path.join(self.dir_data, "model.weights/")

        # vocabulary
        self.filename_words = os.path.join(self.dir_data, "words.txt")
        self.filename_tags = os.path.join(self.dir_data, "tags.txt")
        self.filename_chars = os.path.join(self.dir_data, "chars.txt")

        # Embeddings
        self.filename_glove = os.path.join(self.dir_data, "w2v.txt")
        self.filename_trimmed = os.path.join(self.dir_data, "glove.6B.{}d.trimmed.npz".format(200))

        # Output
        log_path = os.path.join(self.dir_data, "logs.txt")
        self.dir_output = os.path.join(self.dir_data, "results/")

        # Initialize parent class
        super().__init__(log_path=log_path)
