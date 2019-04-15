import os
import logging
from code.util import register
from code.util.db import Submission, Problem
import time
import shutil
import re
from uuid import uuid4

def addSubmission(probId, lang, code, user, type, custominput):
    sub = Submission()
    sub.problem = Problem.get(probId)
    sub.language = lang
    sub.code = code
    sub.result = "pending"
    sub.user = user
    sub.timestamp = time.time() * 1000
    sub.type = type
    sub.status = "review"
    if type == "submit":
        sub.save()
    elif type == "custom":
        sub.custominput = custominput
        sub.id = str(uuid4())
    else:
        sub.id = str(uuid4())
    return sub

exts = {
    "c": "c",
    "cpp": "cpp",
    "cs": "cs",
    "java": "java",
    "python2": "py",
    "python3": "py",
    "ruby": "rb",
    "vb": "vb"
}

def readFile(path):
    try:
        with open(path, "rb") as f:
            return f.read(1000000).decode("utf-8")
    except:
        return None

def strip(text):
    return re.sub("[ \t\r]*\n", "\n", text)

def runCode(sub):
    # Copy the code over to the runner /tmp folder
    extension = exts[sub.language]
    os.mkdir(f"/tmp/{sub.id}")
    with open(f"/tmp/{sub.id}/code.{extension}", "wb") as f:
        f.write(sub.code.encode("utf-8"))
    
    prob = sub.problem
    print("I made it here",sub.type)
    if sub.type == "test":
        tests = prob.samples 
    elif sub.type == "custom":
        
        tests = 1
    else:
        tests = prob.tests     
    # Copy the input over to the tmp folder for the runner
    
    
    for i in range(tests):
        if sub.type != "custom":
            shutil.copyfile(f"/db/problems/{prob.id}/input/in{i}.txt", f"/tmp/{sub.id}/in{i}.txt")
        else:
            with open(f"/tmp/{sub.id}/in{i}.txt", "w") as text_file:
                text_file.write(sub.custominput)
        


    # Output files will go here
    os.mkdir(f"/tmp/{sub.id}/out")

    # Run the runner
    if os.system(f"docker run --rm --network=none -m 256MB -v /tmp/{sub.id}/:/source nathantheinventor/open-contest-dev-{sub.language}-runner {tests} 5 > /tmp/{sub.id}/result.txt") != 0:
        raise Exception("Something went wrong")

    inputs = []
    outputs = []
    answers = []
    errors = []
    results = []
    result = "ok"

    sub.result = "review"
    # TODO:
    # Fix this bug 
    # custom inpout when no test problems
    for i in range(tests):
        if sub.type == "custom":
            inputs.append(sub.custominput)
        else:
            inputs.append(sub.problem.testData[i].input)
        errors.append(readFile(f"/tmp/{sub.id}/out/err{i}.txt"))
        outputs.append(readFile(f"/tmp/{sub.id}/out/out{i}.txt"))
        answers.append(sub.problem.testData[i].output)

        anstrip = strip((answers[-1] or "").rstrip()).splitlines()
        outstrip = strip((outputs[-1] or "").rstrip()).splitlines()

        res = readFile(f"/tmp/{sub.id}/out/result{i}.txt")
        if res == "ok" and anstrip != outstrip:
            extra = False
            if len(anstrip) < len(outstrip):
                extra = True
            incomplete = False
            
            for i in range(len(outstrip)):
                if i < len(anstrip):
                    if anstrip[i] == outstrip[i]:
                        incomplete = True
                    else:
                        extra = False
            if len(anstrip) < len(outstrip):
                incomplete = False

            if not extra and not incomplete:
                res = "wrong_answer"
            elif extra:
                res = "extra_output"
            else:
                res = "incomplete_output"
        if res == None:
            res = "tle"
        if sub.type == "custom":
            res = "ok"
        results.append(res)

        # Make result the first incorrect result
        if res != "ok" and result == "ok":
            result = res

    sub.result = result    
    if(sub.result == "tle" or sub.result == "runtime_error" or sub.result == "ok"):
        sub.status = "judged"
    if(sub.result == "wrong_answer" or sub.result == "extra_output"):
        sub.result == "pending"
    if readFile(f"/tmp/{sub.id}/result.txt") == "compile_error\n":
        sub.results = "compile_error"
        sub.delete()
        sub.compile = readFile(f"/tmp/{sub.id}/out/compile_error.txt")
        shutil.rmtree(f"/tmp/{sub.id}", ignore_errors=True)
        return

    sub.results = results
    sub.inputs = inputs
    sub.outputs = outputs
    sub.answers = answers
    sub.errors = errors

    if sub.type == "submit":
        sub.save()

    shutil.rmtree(f"/tmp/{sub.id}", ignore_errors=True)

def submit(params, setHeader, user):
    probId = params["problem"]
    lang   = params["language"]
    code   = params["code"]
    type   = params["type"]
    custominput = params.get("input")
    submission = addSubmission(probId, lang, code, user, type, custominput)
    runCode(submission)
    return submission.toJSON()

def changeResult(params, setHeader, user):
    id = params["id"]
    vers = params["version"]
    sub = Submission.get(id)    
    if(sub.version != int(vers)):
        return "vErr"    
    if not sub:
        return "Error: incorrect id"
    sub.result = params["result"]
    sub.checkout = None
    sub.version += 1
    sub.save()
    return "ok"

def checkout(params, setHeader, user):
    user_id = params["user_id"]
    subm_id = params["subm_id"]
    sub = Submission.get(subm_id)
    if not sub:
        return "Error: incorrect id"
    if(params["result"] == "yes"):
        sub.checkout = user_id
        sub.save()
        return "ok"
    elif(params["result"] == "no"):
        return "noChange"
    else:
        return "noneSelected"

def changeStatus(params, setHeader, user):
    id = params["id"]
    vers = params["version"]
    sub = Submission.get(id)    
    if(sub.version != int(vers)):
        return "vErr"
    if not sub:
        return "Error: incorrect id"
    sub.status = params["result"]
    sub.checkout = None
    sub.version += 1
    sub.save()
    return "ok"

def resetCheckout(params, setHeader, user):
    id = params["id"]    
    sub = Submission.get(id)    
    
    if not sub:
        return "Error: incorrect id"    
    sub.checkout = None    
    sub.save()
    return "ok"

def rejudge(params, setHeader, user):
    id = params["id"]
    submission = Submission.get(id)
    if os.path.exists(f"/tmp/{id}"):
        shutil.rmtree(f"/tmp/{id}")
    runCode(submission)
    return submission.result


def rejudgeAll(params, setHeader, user):

    ctime = time.time() * 1000
    id = params["id"]
    allsub = Submission.all()
    for i in allsub:
        print(i.result)
        if i.problem.id == id and i.timestamp < ctime and i.result != 'reject':
            rejudge({'id':i.id}, None, None)
    return "Finished"


register.post("/submit", "loggedin", submit)
register.post("/changeResult", "admin", changeResult)
register.post("/changeStatus", "admin", changeStatus)
register.post("/changeCheckout", "admin", checkout)
register.post("/rejudge", "admin", rejudge)
register.post("/rejudgeAll", "admin", rejudgeAll)
register.post("/resetCheckout","admin",resetCheckout)

