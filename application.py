
from flask import Flask, render_template, send_file, request, redirect, url_for, json, abort
from flask_sqlalchemy import SQLAlchemy
from flask_weasyprint import HTML
from werkzeug.exceptions import HTTPException
import sys
import pandas
import os
import os.path
import uuid
import datetime

app = Flask(__name__, static_folder='static', static_url_path='/')
app.config["DEBUG"] = True

##### Database setup #####

SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username=os.getenv("USERNAME"),
    password=os.getenv("PASSWORD"),
    hostname=os.getenv("HOSTNAME"),
    databasename=os.getenv("DATABASENAME"),
)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

##### End database setup #####


##### Maturity model class definitions #####

class Capability:
    def __init__(self, letter, level, focusAreaID, focusAreaName, improvementActions):
        self.letter = letter
        self.level = level
        self.focusAreaID = focusAreaID
        self.focusAreaName = focusAreaName
        self.improvementActions = improvementActions
        self.developedFull = False
        self.developedPartial = False

class FocusArea:
    def __init__(self, name, capabilities):
        self.name = name
        self.capabilities = capabilities
        self.capabilitiesCount = len(capabilities)
        self.maturityLevel = 0
        self.coloringLevelFull = capabilities[0].level - 1
        self.coloringLevelPartial = -1

    def updateMaturity(self, maxLevel):
        index = 0

        for i, capability in enumerate(self.capabilities):
            index = i
            if capability.developedFull:
                self.maturityLevel = capability.level
                if i == len(self.capabilities) - 1:
                    self.coloringLevelFull = maxLevel
            else:
                self.coloringLevelFull = capability.level - 1
                break

        #print(f'index after 1st loop. FA: {self.name}, index: {index}', flush=True)

        for i, capabilityx in enumerate(self.capabilities[index:], start=index):
            #print(f'index: {i}, FA ID: {capabilityx.focusAreaID}, Letter: {capabilityx.letter}, Full?: {capabilityx.developedFull}, partial?: {capabilityx.developedPartial}' , flush=True)
            if (not(capabilityx.developedFull) and capabilityx.developedPartial):
                if i == len(self.capabilities) - 1:
                    self.coloringLevelPartial = maxLevel
            else:
                self.coloringLevelPartial = capabilityx.level - 1
                break

class Level:
    def __init__(self, capabilities):
        self.capabilities = capabilities

class MaturityModel:
    def __init__(self, focusAreas, levels, levelsCount):
        self.focusAreas = focusAreas
        self.focusAreasCount = len(focusAreas)
        self.capabilities = []
        self.levels = levels
        self.levelsCount = levelsCount
        self.maturityLevel = 0
        self.lowestFA = 0
        self.highestFA = 0
        self.improvementCapabilities = []

        for fa in self.focusAreas:
            self.capabilities.append(fa.capabilities)

        self.capabilitiesCount = len(self.capabilities)

    def updateMaturity(self):
        self.lowestFA = min(self.focusAreas, key=lambda fa: fa.coloringLevelFull)
        self.highestFA = max(self.focusAreas, key=lambda fa: fa.coloringLevelFull)
        self.maturityLevel = 0

        for level in self.levels:
            levelAchieved = all(capability.developedFull == True for capability in level.capabilities)
            if levelAchieved:
                self.maturityLevel += 1
            else:
                break

        # Levels start at index 0, which is level 1 in the model.
        if self.maturityLevel == self.levelsCount:
            nextLevel = self.maturityLevel - 1
        else:
            nextLevel = self.maturityLevel

        for capability in self.levels[nextLevel].capabilities:
            if capability.developedFull != True:
                self.improvementCapabilities.append(capability)

##### End maturity model class definitions #####


##### Database tables setup from file #####

# Maturity model.
def createMMTableFromCSV():
    df = pandas.read_csv(os.getenv("ASSETS_PATH") + 'PbD-FAMM.csv', ';', keep_default_na=False)
    df.to_sql('maturitymodel', con=db.engine, if_exists='replace')
    return df

# Assessment questions long (186 questions).
def createAQTableFromCSV():
    df = pandas.read_csv(os.getenv("ASSETS_PATH") + 'assessmentquestions.csv', ';', keep_default_na=False)
    df.to_sql('assessmentquestions', con=db.engine, if_exists='replace')

# Assessment questions short (60 capabilities).
def createAQTableFromCSVShort():
    df = pandas.read_csv(os.getenv("ASSETS_PATH") + 'assessmentquestions_short.csv', ';', keep_default_na=False)
    df.to_sql('assessmentquestionsshort', con=db.engine, if_exists='replace')

# Capability descriptions.
def createCDTableFromCSV():
    df = pandas.read_csv(os.getenv("ASSETS_PATH") + 'capabilitydescriptions.csv', ';', keep_default_na=False)
    df.to_sql('capabilitydescriptions', con=db.engine, if_exists='replace')

# Evaluation questions.
def createEQTableFromCSV():
    df = pandas.read_csv(os.getenv("ASSETS_PATH") + 'evaluationquestions.csv', ';', keep_default_na=False)
    df.to_sql('evaluationquestions', con=db.engine, if_exists='replace')

# Improvement actions.
def createIATableFromCSV():
    df = pandas.read_csv(os.getenv("ASSETS_PATH") + 'improvementactions.csv', ';', keep_default_na=False)
    df.to_sql('improvementactions', con=db.engine, if_exists='replace')

# Start conditions.
def createSCTableFromCSV():
    df = pandas.read_csv(os.getenv("ASSETS_PATH") + 'startconditions.csv', ';', keep_default_na=False)
    df.to_sql('startconditions', con=db.engine, if_exists='replace')

##### End database table setup #####


##### Get data from database #####

# Get maturity model from database.
def getmm():
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM maturitymodel
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    return sql_query.values.tolist()

# Get assessment questions (short) from database.
def getaqs():
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM assessmentquestionsshort
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    df = pandas.DataFrame(sql_query)
    df = df[['Level', 'Question']]
    df = df.groupby('Level').agg(list).reset_index()
    return df['Question'].values.tolist()

# Get assessment questions (short) w/ focus areas from database.
def getaqsFA():
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM assessmentquestionsshort
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    df = pandas.DataFrame(sql_query)
    df = df.sort_values(by=['Level', 'Focus area', 'Question', 'ID'])
    df['Tuples'] = list(zip(df['Focus area'], df['Question']))
    df = df[['Level', 'Tuples']]
    df = df.groupby('Level').agg(list).reset_index()


    #df = df[['Level', 'Question']]
    #df = df.groupby('Level').agg(list).reset_index()
    return df['Tuples'].values.tolist()

# Get capability descriptions from database.
def getcd():
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM capabilitydescriptions
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    return pandas.DataFrame(sql_query)

# Get evaluation questions from database.
def geteq():
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM evaluationquestions
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    return sql_query['Question'].values.tolist()

# Get improvement actions from database.
def getia():
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM improvementactions
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    return pandas.DataFrame(sql_query)

# Get start conditions from database.
def getsc():
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM startconditions
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    return sql_query['Description'].values.tolist()

##### End get data from database #####


##### Helper functions #####

# Create maturity model object
def createMMObject():
    df = createMMTableFromCSV()

    levelsCount = len(df.columns) - 2
    focusAreas = []
    levels = []

    for i in range(0, levelsCount):
        levels.append(Level([]))

    for index, data in df.iterrows():
        row = data.values.tolist()

        # Create new focus area.
        faID = index + 1
        faName = row[0]
        capabilities = []
        iactions = []

        dfiactions = getia()
        dfiactions = dfiactions.groupby(['Focus area', 'Capability']).agg(list).reset_index()

        for i, item in enumerate(row[1:]):
            if isinstance(item, str):
                if item.isalpha():
                    # item is the capability letter as string.

                    # Improvement actions
                    dfRow = dfiactions.loc[(dfiactions['Focus area'] == faID) & (dfiactions['Capability'] == item)]
                    iactions = dfRow['Action'].tolist()[0]

                    # Create new capability.
                    capability = Capability(item, i, faID, faName, iactions)
                    capabilities.append(capability)

                    # Level.
                    levels[i - 1].capabilities.append(capability)

        focusAreas.append(FocusArea(faName, capabilities))

    # Create maturity model.
    maturityModel = MaturityModel(focusAreas, levels, levelsCount)
    return maturityModel

# Quick dirty login prompt.
def password_prompt(message):
    return f'''
                <div style="text-align: center">
                   <form action="/admin" method='post'>
                     <label for="password">{message}</label><br>
                     <input type="password" id="password" name="password" value=""><br>
                     <input type="submit" value="Submit">
                   </form>
                </div>'''

# Format capability descriptions properly.
def createCapabilityDescriptionsList(df):
    df['Tuples'] = tuple(zip(df.Capability, df.Description))
    df = df[['Focus area', 'Tuples']]
    groupeddf = df.groupby('Focus area').agg(list).reset_index()
    return groupeddf['Tuples'].tolist()

# Format assessmentresults properly. (Short)
def formatResultDFShort(data, uniqueID):
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   question
                                   FROM assessmentquestionsshort
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query)#.pop(sql_query.columns[0])
    questionsNumber = len(sql_query.values.tolist())
    df = pandas.DataFrame()

    # Set table headers for the four attributes + number of assessment questions.
    for number in range(0, questionsNumber):
        df.insert(number, 'Question'+str(number+1), pandas.Series(dtype='string'))

    df.insert(0, 'consent', pandas.Series(dtype='bool'))
    df.insert(0, 'endTimeUTC', pandas.Series(dtype='string'))
    df.insert(0, 'startTimeUTC', pandas.Series(dtype='string'))
    df.insert(0, 'dateUTC', pandas.Series(dtype='string'))
    df.insert(0, 'ID', pandas.Series(dtype='string'))

    # Add ID field value
    dataList = list(data.values())
    dataList.insert(0, uniqueID)

    dfValues = pandas.DataFrame([dataList])
    dfValues.columns = df.columns
    df = df.append(dfValues, ignore_index = True)
    return df

# Format evaluationresults properly.
def formatEvaluationDF(data, uniqueID):
    numberOfEvaluationQuestions = db.session.execute('select count(*) from evaluationquestions').first()[0]
    dataList = list(data.values())

    df = pandas.DataFrame()

    # Headers
    for number in range(0, numberOfEvaluationQuestions + 5):
        df.insert(number, 'Question'+str(number+1), pandas.Series(dtype='string'))

    df.insert(0, 'endTimeUTC', pandas.Series(dtype='string'))
    df.insert(0, 'startTimeUTC', pandas.Series(dtype='string'))
    df.insert(0, 'dateUTC', pandas.Series(dtype='string'))
    df.insert(0, 'ID', pandas.Series(dtype='string'))

    # Add ID field value
    dataList.insert(0, uniqueID)

    dfValues = pandas.DataFrame([dataList])
    dfValues.columns = df.columns
    df = df.append(dfValues, ignore_index = True)
    return df

# Format maturity statistics properly.
def formatMaturityStats(maturityModel, uniqueID):
    df = pandas.DataFrame()

    # Headers
    df.insert(0, 'ID', pandas.Series(dtype='string'))
    df.insert(1, 'overallMaturityLevel', pandas.Series(dtype='int'))
    df.insert(2, 'lowestFAName', pandas.Series(dtype='string'))
    df.insert(3, 'lowestFALevel', pandas.Series(dtype='int'))
    df.insert(4, 'highestFAName', pandas.Series(dtype='string'))
    df.insert(5, 'highestFALevel', pandas.Series(dtype='int'))

    for number in range(6, maturityModel.focusAreasCount + 6):
        df.insert(number, 'FA'+str(number-5)+'Level', pandas.Series(dtype='int'))

    # values
    dataList = []
    dataList.insert(0, uniqueID)
    dataList.insert(1, maturityModel.maturityLevel)
    dataList.insert(2, maturityModel.lowestFA.name)
    dataList.insert(3, maturityModel.lowestFA.coloringLevelFull)
    dataList.insert(4, maturityModel.highestFA.name)
    dataList.insert(5, maturityModel.highestFA.coloringLevelFull)

    for focusArea in maturityModel.focusAreas:
        dataList.append(focusArea.coloringLevelFull)

    dfValues = pandas.DataFrame([dataList])
    dfValues.columns = df.columns
    df = df.append(dfValues, ignore_index = True)
    return df

def formatResultsReportShort(answers):
    sql_query = pandas.read_sql_query ('''
                                   SELECT
                                   *
                                   FROM assessmentquestionsshort
                                   ''', con=db.engine)
    pandas.DataFrame(sql_query).pop(sql_query.columns[0])
    df = pandas.DataFrame(sql_query)
    df = df.sort_values(by=['Level', 'Focus area', 'Capability', 'ID'])
    df['Answer'] = answers
    return df

##### End helper functions #####


##### Page rendering #####

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/assessment-intro', methods=('GET', 'POST'))
def assessmentIntro():
    if request.method == 'GET':
        return render_template("assessment-intro.html")
    elif request.method == 'POST':
        data = list(request.form.values())
        if(data[0] == "True"):
            evaluation = True
        else:
            evaluation = False
        return redirect(url_for('assessment', evaluation=evaluation))

@app.route('/assessment/evaluation=<evaluation>', methods=('GET', 'POST'))
def assessment(evaluation):
    if request.method == 'GET':
        return render_template("assessment.html", aq=getaqsFA(), mm=getmm(), consent=evaluation, eq=geteq())
    elif request.method == 'POST':
        uniqueIdentifier = str(uuid.uuid1())

        # Format assessment results and append to database.
        dfResults = formatResultDFShort(request.form, uniqueIdentifier)
        dfResults.to_sql('assessmentresults', con=db.engine, index=False, if_exists='append')

        dfResultsWithAnswers = formatResultsReportShort(dfResults.values.tolist()[0][5:])
        dfResultsWithAnswers = dfResultsWithAnswers.groupby(['Focus area', 'Capability']).agg(list).reset_index()

        # Create maturity model object and populate/update it.
        modelResults = createMMObject()

        for fa in modelResults.focusAreas:
            for capability in fa.capabilities:
                dfCapabilityRow = dfResultsWithAnswers.loc[(dfResultsWithAnswers['Focus area'] == capability.focusAreaID) & (dfResultsWithAnswers['Capability'] == capability.letter)]
                answers = dfCapabilityRow['Answer'].values.tolist()[0]
                #print(f'ID: {capability.focusAreaID}, letter: {capability.letter}, answers: {answers}', flush=True)
                capability.developedFull = all(x == "Yes" for x in answers)
                capability.developedPartial = all(x == "Somewhat" for x in answers)
            fa.updateMaturity(modelResults.levelsCount)
        modelResults.updateMaturity()

        # Format maturity statistics and append to database.
        dfStats = formatMaturityStats(modelResults, uniqueIdentifier)
        dfStats.to_sql('maturitystatistics', con=db.engine, index=False, if_exists='append')

        # Generate report.
        resultsPage = render_template("report.html", aq=getaqs(), cd=createCapabilityDescriptionsList(getcd()), answers=dfResults.values.tolist()[0][5:], mm=getmm(), sc=getsc(), results=modelResults)
        filePath = os.getenv("STATIC_PATH") + 'maturity_reports/' + uniqueIdentifier + '.pdf'
        HTML(string=resultsPage, base_url=os.getenv("STATIC_PATH")).write_pdf(filePath, presentational_hints=True)
        fileSize = f'{str(round(os.stat(filePath).st_size / 1024, 2))} KB'

        return render_template("assessment-result.html", aq=getaqsFA(), cd=createCapabilityDescriptionsList(getcd()), answers=dfResults.values.tolist()[0][5:], mm=getmm(), sc=getsc(), results=modelResults, evaluation=evaluation, uniqueID=uniqueIdentifier, fileSize=fileSize)

@app.route('/evaluation/<uniqueID>', methods=('GET', 'POST'))
def evaluation(uniqueID):
    if request.method == 'GET':
        return render_template("evaluation.html", eq=geteq())
    elif request.method == 'POST':
        dfEvaluation = formatEvaluationDF(request.form, uniqueID)
        dfEvaluation.to_sql('evaluationresults', con=db.engine, index=False, if_exists='append')
        return render_template("evaluation_completed.html")

@app.route('/model')
def model():
    return render_template("model.html", mm=getmm(), cd=createCapabilityDescriptionsList(getcd()), sc=getsc())

@app.route('/research')
def research():
    return render_template("research.html")

@app.route('/terms-and-conditions')
def termsAndConditions():
    return render_template("terms-and-conditions.html")

@app.route('/privacy-policy')
def privacyPolicy():
    return render_template("privacy-policy.html")

@app.route('/sitemap')
def sitemap():
    return render_template("sitemap.html")

@app.route('/test')
def test():
    return render_template("modeltest.html", mm=getmm(), cd=createCapabilityDescriptionsList(getcd()))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'GET':
        return password_prompt("Admin password:")
    elif request.method == 'POST':
        if 'password' in request.form:
            if request.form.get('password') != os.getenv('ADMINPASS'):
                return password_prompt("Invalid password, try again. Admin password:")
        else:
            if 'updatemm' in request.form:
                createMMTableFromCSV()
                return redirect(url_for('model'))
            if 'updateaq' in request.form:  # Long version with 186 questions.
                createAQTableFromCSV()
                return redirect(url_for('assessmentIntro'))
            if 'updateaqs' in request.form: # Short version with 60 focus areas.
                createAQTableFromCSVShort()
                return redirect(url_for('assessmentIntro'))
            if 'updatecd' in request.form:
                createCDTableFromCSV()
                return redirect(url_for('assessmentIntro'))
            if 'updateeq' in request.form:
                createEQTableFromCSV()
                return redirect(url_for('assessmentIntro'))
            if 'updateia' in request.form:
                createIATableFromCSV()
                return redirect(url_for('assessmentIntro'))
            if 'updatesc' in request.form:
                createSCTableFromCSV()
                return redirect(url_for('model'))

    return render_template("admin.html")

@app.route('/download/<fileName>')
def download_results(fileName):
    path = os.getenv("MATURITY_REPORTS_PATH") + fileName + '.pdf'
    fileExists = os.path.isfile(path)
    if fileExists:
        return send_file(path, as_attachment=True, download_name="PbD_maturity_report.pdf")
    else:
        abort(400)

@app.route('/sitemap_index.xml')
def sitemapIndex():
    return render_template("sitemap.xml")

##### End page rendering #####


##### Error Handling #####

@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })

    response.content_type = "application/json"
    return response

##### End error Handling #####


##### Other #####
@app.context_processor
def inject_date():
    return {'today_date': datetime.date.today()}
