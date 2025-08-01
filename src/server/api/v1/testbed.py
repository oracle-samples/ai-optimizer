"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.
"""
# spell-checker:ignore testsets testset selectai giskard litellm

import asyncio
import pickle
import shutil

from datetime import datetime
import json
from typing import Optional
from giskard.rag import evaluate, QATestset
from giskard.rag.metrics import correctness_metric
from fastapi import APIRouter, HTTPException, Header, UploadFile
from fastapi.responses import JSONResponse
import litellm
from langchain_core.messages import ChatMessage
import server.api.core.models as core_models
from server.api.core import settings, databases, oci
from server.api.utils import embed, testbed
from server.api.v1 import chat


import common.schema as schema
import common.logging_config as logging_config

logger = logging_config.logging.getLogger("endpoints.v1.testbed")

auth = APIRouter()


@auth.get(
    "/testsets",
    description="Get Stored TestSets.",
    response_model=list[schema.TestSets],
)
async def testbed_testsets(
    client: schema.ClientIdType = Header(default="server"),
) -> list[schema.TestSets]:
    """Get a list of stored TestSets, create TestSet objects if they don't exist"""
    testsets = testbed.get_testsets(db_conn=databases.get_client_db(client).connection)
    return testsets


@auth.get(
    "/evaluations",
    description="Get Stored Evaluations.",
    response_model=list[schema.Evaluation],
)
async def testbed_evaluations(
    tid: schema.TestSetsIdType,
    client: schema.ClientIdType = Header(default="server"),
) -> list[schema.Evaluation]:
    """Get Evaluations"""
    evaluations = testbed.get_evaluations(db_conn=databases.get_client_db(client).connection, tid=tid.upper())
    return evaluations


@auth.get(
    "/evaluation",
    description="Get Stored Single schema.Evaluation.",
    response_model=schema.EvaluationReport,
)
async def testbed_evaluation(
    eid: schema.TestSetsIdType,
    client: schema.ClientIdType = Header(default="server"),
) -> schema.EvaluationReport:
    """Get Evaluations"""
    evaluation = testbed.process_report(db_conn=databases.get_client_db(client).connection, eid=eid.upper())
    return evaluation


@auth.get(
    "/testset_qa",
    description="Get Stored schema.TestSets Q&A.",
    response_model=schema.TestSetQA,
)
async def testbed_testset_qa(
    tid: schema.TestSetsIdType,
    client: schema.ClientIdType = Header(default="server"),
) -> schema.TestSetQA:
    """Get TestSet Q&A"""
    return testbed.get_testset_qa(db_conn=databases.get_client_db(client).connection, tid=tid.upper())


@auth.delete(
    "/testset_delete/{tid}",
    description="Delete a TestSet",
)
async def testbed_delete_testset(
    tid: Optional[schema.TestSetsIdType] = None,
    client: schema.ClientIdType = Header(default="server"),
) -> JSONResponse:
    """Delete TestSet"""
    testbed.delete_qa(databases.get_client_db(client).connection, tid.upper())
    return JSONResponse(status_code=200, content={"message": f"TestSet: {tid} deleted."})


@auth.post(
    "/testset_load",
    description="Upsert TestSets.",
    response_model=schema.TestSetQA,
)
async def testbed_upsert_testsets(
    files: list[UploadFile],
    name: schema.TestSetsNameType,
    tid: Optional[schema.TestSetsIdType] = None,
    client: schema.ClientIdType = Header(default="server"),
) -> schema.TestSetQA:
    """Update stored TestSet data"""
    created = datetime.now().isoformat()
    db_conn = databases.get_client_db(client).connection
    try:
        for file in files:
            file_content = await file.read()
            content = testbed.jsonl_to_json_content(file_content)
            db_id = testbed.upsert_qa(db_conn, name, created, content, tid)
        db_conn.commit()
    except Exception as ex:
        logger.error("An exception occurred: %s", ex)
        raise HTTPException(status_code=500, detail="Unexpected Error.") from ex

    testset_qa = await testbed_testset_qa(client=client, tid=db_id)
    return testset_qa


@auth.post(
    "/testset_generate",
    description="Generate Q&A Test Set.",
    response_model=schema.TestSetQA,
)
async def testbed_generate_qa(
    files: list[UploadFile],
    name: schema.TestSetsNameType,
    ll_model: schema.ModelIdType = None,
    embed_model: schema.ModelIdType = None,
    questions: int = 2,
    client: schema.ClientIdType = Header(default="server"),
) -> schema.TestSetQA:
    """Retrieve contents from a local file uploaded and generate Q&A"""
    # Setup Models
    giskard_ll_model = core_models.get_model(model_id=ll_model, model_type="ll")
    giskard_embed_model = core_models.get_model(model_id=embed_model, model_type="embed")
    temp_directory = embed.get_temp_directory(client, "testbed")
    full_testsets = temp_directory / "all_testsets.jsonl"

    for file in files:
        try:
            # Read and save file content
            file_content = await file.read()
            filename = temp_directory / file.filename
            logger.info("Writing Q&A File to: %s", filename)
            with open(filename, "wb") as file:
                file.write(file_content)

            # Process file for knowledge base
            text_nodes = testbed.load_and_split(filename)
            test_set = testbed.build_knowledge_base(text_nodes, questions, giskard_ll_model, giskard_embed_model)
            # Save test set
            test_set_filename = temp_directory / f"{name}.jsonl"
            test_set.save(test_set_filename)
            with (
                open(test_set_filename, "r", encoding="utf-8") as source,
                open(full_testsets, "a", encoding="utf-8") as destination,
            ):
                destination.write(source.read())
        except litellm.APIConnectionError as ex:
            shutil.rmtree(temp_directory)
            logger.error("APIConnectionError Exception: %s", str(ex))
            raise HTTPException(status_code=424, detail=str(ex)) from ex
        except Exception as ex:
            shutil.rmtree(temp_directory)
            logger.error("Unknown TestSet Exception: %s", str(ex))
            raise HTTPException(status_code=500, detail=f"Unexpected testset error: {str(ex)}.") from ex

        # Store tests in database
        with open(full_testsets, "rb") as file:
            upload_file = UploadFile(file=file, filename=full_testsets)
            testset_qa = await testbed_upsert_testsets(client=client, files=[upload_file], name=name)
        shutil.rmtree(temp_directory)

    return testset_qa


@auth.post(
    "/evaluate",
    description="Evaluate Q&A Test Set.",
    response_model=schema.EvaluationReport,
)
def testbed_evaluate_qa(
    tid: schema.TestSetsIdType,
    judge: schema.ModelIdType,
    client: schema.ClientIdType = Header(default="server"),
) -> schema.EvaluationReport:
    """Run evaluate against a testset"""

    def get_answer(question: str):
        """Submit question against the chatbot"""
        request = schema.ChatRequest(
            messages=[ChatMessage(role="human", content=question)],
        )
        ai_response = asyncio.run(chat.chat_post(client=client, request=request))
        return ai_response.choices[0].message.content

    evaluated = datetime.now().isoformat()
    client_settings = settings.get_client_settings(client)
    # Change Disable History
    client_settings.ll_model.chat_history = False
    # Change Grade vector_search
    client_settings.vector_search.grading = False

    db_conn = databases.get_client_db(client).connection
    testset = testbed.get_testset_qa(db_conn=db_conn, tid=tid.upper())
    qa_test = "\n".join(json.dumps(item) for item in testset.qa_data)
    temp_directory = embed.get_temp_directory(client, "testbed")

    with open(temp_directory / f"{tid}_output.txt", "w", encoding="utf-8") as file:
        file.write(qa_test)
    loaded_testset = QATestset.load(temp_directory / f"{tid}_output.txt")

    # Setup Judge Model
    logger.debug("Starting evaluation with Judge: %s", judge)
    oci_config = oci.get_oci(client)
    judge_client = core_models.get_client({"model": judge}, oci_config, True)
    try:
        report = evaluate(get_answer, testset=loaded_testset, llm_client=judge_client, metrics=[correctness_metric])
    except KeyError as ex:
        if str(ex) == "'correctness'":
            raise HTTPException(status_code=500, detail="Unable to determine the correctness; please retry.") from ex

    logger.debug("Ending evaluation with Judge: %s", judge)

    eid = testbed.insert_evaluation(
        db_conn=db_conn,
        tid=tid,
        evaluated=evaluated,
        correctness=report.correctness,
        settings=client_settings.model_dump_json(),
        rag_report=pickle.dumps(report),
    )
    db_conn.commit()
    shutil.rmtree(temp_directory)

    return testbed.process_report(db_conn=db_conn, eid=eid)
