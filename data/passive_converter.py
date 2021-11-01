import math
import pickle

### Constants and stuff
#distances for node clusters
orbit_radius=[0, 82, 162, 335, 493, 662, 846]
skills_per_orbit=[1,6,12,12,40,72,72]

# aoe of timeless jewels
jewel_radius=1800 #just a guess, but it's below 1807 and above 1796

# scale for 1080 resolution
res_scale=1.08/10

### Jewel socket node numbers, in a nice order 
# order is clockwise, three loops around the tree, starting in the life/mana scion wheel, ending next to point blank
socket_ids=[6230 , 48768 , 31683 , 
28475, 33631 , 36634 , 41263 , 33989 , 34483 , 
54127, 2491 , 26725 , 55190 , 26196 , 7960 , 61419 , 21984 , 61834 , 32763 , 60735 , 46882]

### read in the whole passive tree into lined_input
raw_input = open("passive-skill-tree",encoding='utf-8')
lined_input = raw_input.readlines()
total_lines=len(lined_input)


### define my crappy text-detection script
def text_in_line(line_number,sample_text):
	line=lined_input[line_number]
	if len(line)<len(sample_text):
		return False
	for i in range(len(line)-len(sample_text)):
		k=0
		Same=True
		while Same and k<len(sample_text):
			if sample_text[k]==line[i+k]:
				k+=1
			else:
				Same=False
		if Same:
			return True
	return False


### find the start of the coordinates
target_text='"groups": {'
current_line=0
Same=True
while current_line<total_lines:
	if text_in_line(current_line,target_text):
		break
	current_line+=1
#print(lined_input[current_line])

### encode the coordinates for a group
group_coords=[(0,0) for n in range(1000)]
group_name=1
group_name_str='"'+str(group_name)+'": {'
#print(group_name_str)
end_trigger_text='"nodes": {'
while current_line<total_lines:
	if text_in_line(current_line,group_name_str):
		#read next two lines for the coordinates
		xline=lined_input[current_line+1]
		yline=lined_input[current_line+2]
		#print(xline)
		#print(yline)
		xpos=0
		while xline[xpos]!='x':
			xpos+=1
		ypos=0
		while yline[ypos]!='y':
			ypos+=1
		xcom=xpos
		while xline[xcom]!=',':
			xcom+=1
		ycom=ypos
		while yline[ycom]!=',':
			ycom+=1
		xcoord=xline[xpos+4:xcom]
		ycoord=yline[ypos+4:ycom]
		#print(xcoord,ycoord,float(xcoord),float(ycoord))
		group_coords[group_name]=(float(xcoord),float(ycoord))
		group_name+=1
		group_name_str='"'+str(group_name)+'": {'
		#print(group_name_str)
	current_line+=1
	#print(text_in_line(current_line,group_name_str),current_line,lined_input[current_line])
	if text_in_line(current_line,end_trigger_text):
		break
#print(group_name,current_line)
group_str='"group":'

node_list=[]
next_node_trigger='        },'
end_trigger='    },'
non_skills=['ascendancyName','Small Jewel Socket','Medium Jewel Socket','isBlighted','isMastery','isProxy','classStart']
while current_line<total_lines:
	if lined_input[current_line][:10]==next_node_trigger:
		#add the next node into the node list
		node_num_line=lined_input[current_line+2]
		node_pos=0
		while node_num_line[node_pos]!=':':
			node_pos+=1
		node_com=node_pos
		while node_num_line[node_com]!=',':
			node_com+=1
		node=int(node_num_line[node_pos+1:node_com])
		#find group,orbit, orbitIndex
		i=0
		while i<100:
			is_skill=True
			for non_skill_text in non_skills:
				if text_in_line(current_line+i,non_skill_text):
					is_skill=False
					break
			if not is_skill:
				break
			if text_in_line(current_line+i,group_str):
				group_com=22
				while lined_input[current_line+i][group_com]!=',':
					group_com+=1
				orbit_com=22
				while lined_input[current_line+i+1][orbit_com]!=',':
					orbit_com+=1
				orbitIndex_com=26
				while lined_input[current_line+i+2][orbitIndex_com]!=',':
					orbitIndex_com+=1
				group=int(lined_input[current_line+i][21:group_com])
				orbit=int(lined_input[current_line+i+1][21:orbit_com])
				orbitIndex=int(lined_input[current_line+i+2][26:orbitIndex_com])
				node_list.append((node,group,orbit,orbitIndex))
				break
			i+=1
	current_line+=1
	if lined_input[current_line][:6]==end_trigger:
		break
	if current_line>68000:
		break

### finished reading in the file

#draw a picture to figure out the scaling coefficient
#same loop to make a dictionary of node coordinates

#from PIL import Image, ImageDraw
#img = Image.new('RGB', (5000,5000), color = (0,0,0))
#d=ImageDraw.Draw(img)
node_coords={}
for n in node_list:
	x_val=0
	y_val=0
	x_val+=group_coords[n[1]][0]
	y_val+=group_coords[n[1]][1]
	x_shift=math.sin(math.radians(360*n[3]/skills_per_orbit[n[2]]))
	y_shift=-math.cos(math.radians(360*n[3]/skills_per_orbit[n[2]]))
	x_val+=orbit_radius[n[2]]*x_shift
	y_val+=orbit_radius[n[2]]*y_shift
	#transformation for fully zoomed out 1920x1080
	#x_val=x_val/10*1.08+2500
	#y_val=y_val/10*1.08+2500
	#d.text((x_val,y_val),str(n[0]),fill=(255,255,255))
	#d.ellipse((x_val-2,y_val-2,x_val+2,y_val+2),fill=(255,255,255))
	node_coords[n[0]]=(x_val,y_val)
#img.save("passive_picture.png")

### finding jewel radius
#jewel socket between templar and marauder is 33631
#mana and reduced cost (next to sanctity) is not in radius 31819
#a strength node is in radius 50422
#j=node_coords[33631]
#outside=node_coords[31819]
#inside=node_coords[50422]
#print(math.sqrt((j[0]-outside[0])**2+(j[1]-outside[1])**2))
#print(math.sqrt((j[0]-inside[0])**2+(j[1]-inside[1])**2))

### make a dictionary with all the nodes next to sockets
neighbor_nodes={}
for socket in socket_ids:
	socket_coords=node_coords[socket]
	socket_neighbors=[]
	for n in node_list:
		if n[0] in socket_ids:
			continue
		n_coords=node_coords[n[0]]
		if math.sqrt((socket_coords[0]-n_coords[0])**2+(socket_coords[1]-n_coords[1])**2)<jewel_radius:
			socket_neighbors.append(n[0])
	neighbor_nodes[socket]=list(socket_neighbors)

f = open("processed_tree.pckl", 'wb')
pickle.dump(node_coords,f)
pickle.dump(neighbor_nodes,f)
	