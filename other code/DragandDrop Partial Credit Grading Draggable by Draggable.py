
import json
   
def hint_fn(answer_ids, student_answers, new_cmap, old_cmap):
    ###Load Student Input. Student_answers[aid] is unicode until evaluated to a list.
    aid = answer_ids[0]	
    student_dnd_input = eval(student_answers[aid])

	##########################
    ####ONLY EDIT BELOW HERE! Enter your correct answers as a list of dictionaries.
    parts = [
            {'1':[[205,277],18]},
            {'1':[[273,277],18]},
            {'1':[[273,458],18]},
            {'1':[[273,479],18]}
            ]
	#####ONLY EDIT ABOVE HERE!
 	##########################

    max_score = len(parts)
    total_score = 0
    for part in parts:
        for draggable in student_dnd_input:
			##Draganddrop.grade expects a json file made from a *list* of dictionaries.
			##Draganddrop.grade returns boolean 1 or 0.
            draggable = json.dumps([draggable,])
            part_ok = draganddrop.grade(draggable,part)
            if part_ok:
                total_score += 1
				##To be sure that each draggable only gets credit once, break here.
                break
    
	##In case extra draggables were added, subtract excess from score.
    extra = max(0,len(student_dnd_input)-max_score)
    missing = len(student_dnd_input)-max_score
    total_score = max(0,total_score-extra)

    overall_msg = "<span style='color:blue'/>" + str(total_score+extra) + " out of " + str(max_score+missing) + " of your dragged bands are correct.</span>"

    if total_score / max_score == 1:
        overall_msg += " <img src='/static/greencheck.png' alt='A green check mark'/>"
    else:
        overall_msg += " <img src='/static/redX.png' alt='A red X'/>"
    
    new_cmap.set_hint_and_mode(aid, overall_msg, 'always')
    new_cmap.set_property(aid, 'npoints', round(total_score / max_score, 2))    
