<script type="text/python" system_path="python_lib">


import json
   
def hint_fn(answer_ids, student_answers, new_cmap, old_cmap):
    ###Load Student Input. Student_answers[aid] is unicode until evaluated to a list.
    aid = answer_ids[0] 
    student_dnd_input = eval(student_answers[aid])

    ##########################
    ####Enter all possible answers as a list of dictionaries.
    parts = [{'1':'t1'},{'1':'t2'},{'1':'t3'},{'1':'t4'},{'1':'t5'},{'1':'t6'},{'1':'t7'},{'1':'t8'},{'1':'t9'},{'1':'t10'},{'1':'t11'},{'1':'t12'},{'2':'t1'},{'2':'t2'},{'2':'t3'},{'2':'t4'},{'2':'t5'},{'2':'t6'},{'2':'t7'},{'2':'t8'},{'2':'t9'},{'2':'t10'},{'2':'t11'},{'2':'t12'}]
    #####
    ##########################

    #This dict keeps track of which symbol, + or -, students dragged to the correct answers.
    cuts = {'t1':'', 't2':'', 't3':'', 't4':'', 't5':'', 't6':'', 't7':'', 't8':'', 't9':'', 't10':'', 't11':'', 't12':''}
    total_score = 0
    for draggable in student_dnd_input:
        jdraggable = json.dumps([draggable,])
        for part in parts:
            ##Draganddrop.grade expects a json file made from a *list* of dictionaries.
            ##Draganddrop.grade returns boolean 1 or 0.
            if draganddrop.grade(jdraggable,part):
                #Assigns the key name (the color dot, in 1 or 2 form) to the target site dict
                cuts[draggable.values()[0]] = draggable.keys()[0]
    
    #Gives students a point for correct lane.
    max_score = 4
    lane1 = cuts['t1'] == cuts['t5'] and cuts['t5'] == cuts['t9'] and cuts['t1'] == '2'
    lane2 = cuts['t2'] == cuts['t6'] and cuts['t2'] == '2' and cuts['t10'] == '1'
    lane3 = cuts['t7'] == cuts['t11'] and cuts['t7'] == '1' and cuts['t3'] == '2'
    lane4 = cuts['t4'] == cuts['t12'] and cuts['t4'] == '1' and cuts['t8'] == '2'

    if lane1:
        total_score += 1
    if lane2:
        total_score += 1
    if lane3:
        total_score += 1
    if lane4:
        total_score += 1

    #Customized feedback space.

    overall_msg = "&lt;span style='color:blue'/&gt;"
    
    if not lane1:
        overall_msg += "Take another look at your labeling for lane 1. "
    if not lane2:
        overall_msg += "Take another look at your labeling for lane 2. "
    if not lane3:
        overall_msg += "Take another look at your labeling for lane 3. "
    if not lane4:
        overall_msg += "Take another look at your labeling for lane 4. "

    overall_msg += "&lt;/span&gt;"
    #Adds the expected green check and red X to the message, since students need that.
    if total_score / max_score == 1:
        overall_msg += " &lt;img src='/static/greencheck.png' alt='A green check mark'/&gt;"
    else:
        overall_msg += " &lt;img src='/static/redX.png' alt='A red X'/&gt;"
    
    #Send their grade back to the problem.
    new_cmap.set_hint_and_mode(aid, overall_msg, 'always')
    new_cmap.set_property(aid, 'npoints', round(total_score / max_score, 2))    


</script>


<customresponse>
    <drag_and_drop_input img="/static/Q2_partB_RNASecretComponent.png" target_outline="true">
      <draggable id="1" label="+" can_reuse="true"/>
      <draggable id="2" label="-" can_reuse="true"/>
      <target id="t1" x="156" y="80" w="26" h="26"/>
      <target id="t2" x="207" y="80" w="26" h="26"/>
      <target id="t3" x="259" y="80" w="26" h="26"/>
      <target id="t4" x="311" y="80" w="26" h="26"/>
      <target id="t5" x="156" y="112" w="26" h="26"/>
      <target id="t6" x="207" y="112" w="26" h="26"/>
      <target id="t7" x="259" y="112" w="26" h="26"/>
      <target id="t8" x="311" y="112" w="26" h="26"/>
      <target id="t9" x="156" y="156" w="26" h="26"/>
      <target id="t10" x="207" y="156" w="26" h="26"/>
      <target id="t11" x="259" y="156" w="26" h="26"/>
      <target id="t12" x="311" y="156" w="26" h="26"/>
    </drag_and_drop_input>
    <hintgroup hintfn="hint_fn"/>
  </customresponse>