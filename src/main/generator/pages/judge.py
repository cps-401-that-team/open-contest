from code.util import register
from code.util.db import Contest, Problem, Submission
from code.generator.lib.htmllib import *
from code.generator.lib.page import *
from difflib import *
import logging
from datetime import datetime

class ProblemTab(UIElement):
    def __init__(self, x):
        num, prob = x
        self.html = h.li(
            h.a(prob.title, href=f"#tabs-{num}")
        )

icons = {
    "ok": "check",
    "wrong_answer": "times",
    "tle": "clock",
    "runtime_error": "exclamation-triangle",
    "presentation_error": "times",
    "extra_output": "times",
    "pending": "sync"
}
verdict_name = {
    "ok": "Accepted",
    "wrong_answer": "Wrong Answer",
    "tle": "Time Limit Exceeded",
    "runtime_error": "Runtime Error",
    "presentation_error": "Presentation Error",
    "extra_output": "Extra Output",
    "pending": "Pending..."
}

def resultOptions(result):
    ans = []
    for res in verdict_name:
        if result == res:
            ans.append(h.option(verdict_name[res], value=res, selected="selected"))
        else:
            ans.append(h.option(verdict_name[res], value=res))
    return ans

class TestCaseTab(UIElement):
    def __init__(self, x, sub):
        num, result = x
        self.html = h.li(
            h.a(href=f"#tabs-{sub.id}-{num}", contents=[
                h.i(cls=f"fa fa-{icons[result]}", title=f"{verdict_name[result]}"),
                f"Sample #{num}"
            ])
        )

def markDiffLines(user,ans):

    #diff wrapers
    spanred = '<span style="background:red">' #red=lines are different
    spangreen = '<span style="background:#19ad19">'#green = line only exists in this list
    spanlightred = '<p style="margin:0;background:#ff9999">'
    spanlightgreen ='<p style="margin:0;background:#1aff1a">'
    end = '</span>'
    lightend = '</p>'
    rows = 0

    if len(user) > len(ans):
        rows = len(user)
        big = user
        small = ans
    else:
        rows = len(ans)
        big = ans
        small = user

    for i in range(rows):
        if i < len(small):
            bl = 0
            sl = 0
            tempbig = ''
            tempsmall = ''
            same = True
            #find matching sections of strings
            for match in SequenceMatcher(None, big[i], small[i]).get_matching_blocks():
                if same and match.a != big[i][-1]:
                    same = False
                #mark sections that differ from the other string
                tempbig += (((spanred if big==user else spangreen) + big[i][bl:match.a]+ end) if len(big[i][bl:match.a]) > 0 else "") + big[i][match.a:match.a+match.size]
                bl = match.a+match.size
                                                 
                tempsmall += (( (spanred if small==user else spangreen)+ small[i][sl:match.b]+ end) if len(small[i][sl:match.b]) > 0 else "") + small[i][match.b:match.b+match.size]
                sl = match.b+match.size
                
            if not same:
                big[i] = (spanlightred if big == user else spanlightgreen) + tempbig + lightend
                small[i] = (spanlightred if small == user else spanlightgreen) + tempsmall + lightend
            else:
                big[i] = tempbig
                small[i] = tempsmall

        else:
            big[i] = (spanlightred if big==user else spanlightgreen)+big[i]+lightend




class TestCaseData(UIElement):
    def __init__(self, x, sub):
        num, input, output, error, answer = x

        #prepare formmat for function
        answer = answer.replace(" ", "&nbsp;").splitlines()
        output = output.replace(" ", "&nbsp;").splitlines()

        #modify output and answer strings to display differences by color
        markDiffLines(output,answer)
        
        #restore format
        answer = ''.join(answer)
        output = ''.join(output)
        
        
        self.html = div(id=f"tabs-{sub.id}-{num}", contents=[
            div(cls="row", contents=[
                div(cls="col-12", contents=[
                    h.h4("Input"),
                    h.code(input.replace(" ", "&nbsp;").replace("\n", "<br/>"))
                ])
            ]),
            div(cls="row", contents=[
                div(cls="col-6", contents=[
                    h.h4("Output"),
                    h.code(output)
                    
                ]),
                div(cls="col-6", contents=[
                    h.h4("Correct Answer"),
                    h.code(answer)
                ])
            ])
        ])

class SubmissionCard(UIElement):
    def __init__(self, submission: Submission):
        subTime = submission.timestamp
        probName = submission.problem.title
        cls = "red" if submission.result != "ok" else ""
        self.html = div(cls="modal-content", contents=[
            div(cls=f"modal-header {cls}", contents=[
                h.h5(
                    f"Submission to {probName} at ",
                    h.span(subTime, cls="time-format")
                ),
                """
                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>"""
            ]),
            div(cls="modal-body", contents=[
                h.strong("Language: <span class='language-format'>{}</span>".format(submission.language)),
                h.br(),
                h.strong("Result: ",
                    h.select(cls=f"result-choice {submission.id}", onchange=f"changeSubmissionResult('{submission.id}')", contents=[
                        *resultOptions(submission.result)
                    ])
                ),
                h.br(),
                h.br(),
                h.button("Rejudge", type="button", onclick=f"rejudge('{submission.id}')", cls="btn btn-primary rejudge"),
                h.br(),
                h.br(),
                h.strong("Code:"),
                h.code(submission.code.replace("\n", "<br/>").replace(" ", "&nbsp;"), cls="code"),
                div(cls="result-tabs", id="result-tabs", contents=[
                    h.ul(*map(lambda x: TestCaseTab(x, submission), enumerate(submission.results))),
                    *map(lambda x: TestCaseData(x, submission), zip(range(submission.problem.tests), submission.inputs, submission.outputs, submission.errors, submission.answers))
                ])
            ])
        ])

class ProblemContent(UIElement):
    def __init__(self, x, cont):
        num, prob = x
        subs = filter(lambda sub: sub.problem == prob and cont.start <= sub.timestamp <= cont.end, Submission.all())
        self.html = div(*map(SubmissionCard, subs), id=f"tabs-{num}")

class SubmissionRow(UIElement):
    def __init__(self, sub):
        self.html = h.tr(
            h.td(sub.user.username),
            h.td(sub.problem.title),
            h.td(cls='time-format', contents=sub.timestamp),
            h.td(sub.language),
            h.td(
                h.i("&nbsp;", cls=f"fa fa-{icons[sub.result]}"),
                h.span(verdict_name[sub.result])
            ),
            onclick=f"submissionPopup('{sub.id}')"
        )

class SubmissionTable(UIElement):
    def __init__(self, contest):
        subs = filter(lambda sub: sub.user.type != "admin" and contest.start <= sub.timestamp <= contest.end, Submission.all())
        self.html = h.table(
            h.thead(
                h.tr(
                    h.th("Name"),
                    h.th("Problem"),
                    h.th("Time"),
                    h.th("Language"),
                    h.th("Result")
                )
            ),
            h.tbody(
                *map(lambda sub: SubmissionRow(sub), subs)
            ),
            id="submissions"
        )

def judge(params, user):
    cont = Contest.getCurrent()
    if not cont:
        return Page(
            h1("&nbsp;"),
            h1("No Contest Available", cls="center")
        )
    
    return Page(
        h2("Judge Submissions", cls="page-title"),
        div(id="judge-table", contents=[
            SubmissionTable(cont)
        ]),
        div(cls="modal", tabindex="-1", role="dialog", contents=[
            div(cls="modal-dialog", role="document", contents=[
                div(id="modal-content")
            ])
        ])
    )

def judge_submission(params, user):
    return SubmissionCard(Submission.get(params[0]))

register.web("/judgeSubmission/([a-zA-Z0-9-]*)", "admin", judge_submission)
register.web("/judge", "admin", judge)
