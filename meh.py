r"""
  __  __ ______ _    _ _
 |  \/  |  ____| |  | | |
 | \  / | |__  | |__| | |
 | |\/| |  __| |  __  | |
 | |  | | |____| |  | |_|
 |_|  |_|______|_|  |_(_) My Expert Helper

## Overview

A simple conversational app powered by LangChain and Streamlit that

1. Takes in a user prompt
2. Translates it to a target language using Amazon Translate
3. Sends it to Anthropic's Claude on Amazon Bedrock
4. Translates the response back to the source language
5. Turns the response into speech via Amazon Polly

**Why?** Because... meeeeeeeeeeh! 🐑

Why? Because... meh!

## Instructions

Download and install FFmpeg

> https://www.ffmpeg.org/download.html

Install dependencies

> pip install -qU boto3 botocore pydub streamlit

Run the application

> streamlit run meh.py
"""

import io
import os
import re

import boto3
import botocore

import streamlit as st

from langchain.chat_models import BedrockChat
from langchain.prompts import ChatPromptTemplate

from pydub import AudioSegment
from pydub.playback import play

#################
# Initial Setup #
#################

st.title("MEH! 😒")
st.subheader("**M**y **E**xpert **H**elper")

# Initialize boto3 clients
session = boto3.Session()
bedrock = session.client('bedrock')
polly = session.client('polly')
translate = session.client('translate')

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

@st.cache_data
def lst_langs():
    """Returns a list of languages supported by Amazon Translate"""
    return translate.list_languages()['Languages']

@st.cache_data
def transl_txt(input_txt, src_lang, tgt_lang):
    """Translates input text from the source language to the target language"""
    return translate.translate_text(
        Text=input_txt,
        SourceLanguageCode=src_lang,
        TargetLanguageCode=tgt_lang
    )['TranslatedText']

# List available languages
langs = lst_langs()

# Select a source and a target language
st.sidebar.selectbox(
    label='Source Language',
    options=langs,
    index=langs.index(next(filter(lambda n: n.get('LanguageCode') == 'pt-PT', langs))),
    format_func=lambda lang: f"{lang['LanguageName']} ({lang['LanguageCode']})",
    key='src_lang'
)

st.sidebar.selectbox(
    label='Target Language',
    options=langs,
    index=langs.index(next(filter(lambda n: n.get('LanguageCode') == 'en', langs))),
    format_func=lambda lang: f"{lang['LanguageName']} ({lang['LanguageCode']})",
    key='tgt_lang'
)

# Should I play an audio of the assistant response?
audio_enabled = st.sidebar.checkbox(
    label='Audio',
    value=False,
    key='audio_enabled'
)

# Translate -> Polly language map
lang_map = {
    'en': 'en-US',
    'pt': 'pt-BR'
}

@st.cache_data
def get_voices(tgt_lang, engine='neural'):
    """Returns the list of voices that are available for use for a specific language"""
    tgt_lang = lang_map.get(tgt_lang, tgt_lang)
    try:
        return polly.describe_voices(
            Engine=engine,
            LanguageCode=tgt_lang,
            IncludeAdditionalLanguageCodes=False
        )['Voices']
    except botocore.exceptions.ClientError as err:
        st.warning(err)
        return []

if audio_enabled:
    voices = get_voices(st.session_state.src_lang['LanguageCode'])
    st.sidebar.selectbox(
        label='Voice',
        options=voices,
        format_func=lambda voice: voice['Id'],
        key='voice'
    )

def play_it(text, lang_code, voice_id, engine='neural', output_format='mp3'):
    """Synthesizes an input string to a stream of bytes"""
    lang_code = lang_map.get(lang_code, lang_code)
    audio_data = polly.synthesize_speech(
        Engine=engine,               # standard|neural|long-form,
        LanguageCode=lang_code,
        OutputFormat=output_format,  # json|mp3|ogg_vorbis|pcm
        Text=text,
        TextType='text',
        VoiceId=voice_id,
    )
    audio_msg = AudioSegment.from_file(
        io.BytesIO(
            audio_data['AudioStream'].read()
        )
    )
    play(audio_msg)

##########
# Chains #
##########

# For a description of each inference parameter, see
# https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-claude.html
model_kwargs = {
    "temperature":
        float(os.getenv("BEDROCK_JCVD_TEMPERATURE", "0.1")),
    "top_p":
        float(os.getenv("BEDROCK_JCVD_TOP_P", "1")),
    "top_k":
        int(os.getenv("BEDROCK_JCVD_TOP_K", "250")),
    "max_tokens_to_sample":
        int(os.getenv("BEDROCK_JCVD_MAX_TOKENS_TO_SAMPLE", "300"))
}

@st.cache_data
def lst_models():
    """Lists all Anthropic models"""
    return bedrock.list_foundation_models(byProvider='Anthropic')['modelSummaries']

# Full list of base model IDs is available at
# https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids-arns.html
models = lst_models()
st.sidebar.selectbox(
    label='Model',
    options=models,
    index=models.index(next(filter(lambda n: n.get('modelId') == 'anthropic.claude-v2', models))),
    format_func=lambda model: model['modelId'],
    key='model'
)

# For some tips on how to construct effective prompts for Claude,
# check out Anthropic's Claude Prompt Engineering deck (Bedrock edition)
# https://docs.google.com/presentation/d/1tjvAebcEyR8la3EmVwvjC7PHR8gfSrcsGKfTPAaManw
prompt = ChatPromptTemplate.from_messages([("human", "{input}")])

# For more information on how Bedrock integrates with LangChain, see
# https://python.langchain.com/docs/integrations/chat/bedrock
model = BedrockChat(
    model_id=st.session_state.model['modelId'],
    model_kwargs=model_kwargs
)

chain = prompt | model

###########
# Chat UI #
###########

def process_response(output):
    """Transforms the model output before sending it to the AI services"""
    # Do *not* translate code samples
    # https://aws.amazon.com/blogs/machine-learning/amazon-translate-now-enables-you-to-mark-content-to-not-get-translated/
    output = re.sub(
        r"```(.*?)```",
        r"<p translate=no>\n\n```\1```\n\n</p>",
        output,
        flags=re.DOTALL
    )
    return output

def clean_html_tags(output):
    """Removes all HTML tags from a string"""
    output = re.sub(r"<.*?>", "", output)
    return output

# Add a big red button to clear past messages
st.markdown("""
<style>
div.stButton > button:first-child {
    background-color: red;
    color: white;
}
</style>""", unsafe_allow_html=True)

if st.sidebar.button('Clear chat history'):
    st.session_state.messages = []

# Display messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
    with st.chat_message("translator", avatar="🗣️"):
        st.markdown(message["translation"])

# Prompt user for input
if prompt := st.chat_input():
    # Translate user prompt
    transl_prompt = transl_txt(
        prompt,
        st.session_state.src_lang['LanguageCode'],
        st.session_state.tgt_lang['LanguageCode']
    )

    # Add user prompt to chat history
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
            "translation": transl_prompt
        }
    )

    # Display user prompt
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("translator", avatar="🗣️"):
        st.markdown(transl_prompt)

    with st.chat_message("assistant"):
        # Call the assistant model
        response = chain.invoke({
            'input': transl_prompt
        }).content

        # Translate the response
        proc_response = process_response(response)
        transl_response = transl_txt(
            proc_response,
            st.session_state.tgt_lang['LanguageCode'],
            st.session_state.src_lang['LanguageCode']
        )
        transl_response = clean_html_tags(transl_response)

        # Display assistant response
        st.markdown(response)

    with st.chat_message("translator", avatar="🗣️"):
        st.markdown(transl_response)

    # Play assistant response
    if audio_enabled:
        play_it(
            transl_response,
            st.session_state.src_lang['LanguageCode'],
            st.session_state.voice['Id']
        )

    # Add assistant response to chat history
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response,
            "translation": transl_response
        }
    )

st.sidebar.markdown("""
### What is MEH!?                    

MEH! is a simple conversational app powered by LangChain and Streamlit that 1/ takes in a user prompt, 2/ translates it to a target language using [Amazon Translate](https://aws.amazon.com/translate/), 3/ sends it to [Anthropic's Claude on Amazon Bedrock](https://aws.amazon.com/bedrock/claude/), 4/ translates the response back to the source language, and 5/ **optional** turns the response into speech via [Amazon Polly](https://aws.amazon.com/polly/). 
            
**Why?** Because... meeeeeeeeeeh! 🐑
""")
