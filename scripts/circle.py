import math



center = [478110, 3638661]



angles = [90, 120, 150, 180, 210, 240, 270, 300, 330, 0, 30, 60, 90]

plots = []

for angle in angles:
    radAng = math.radians(angle)
    xdiff = 100 * (math.cos(radAng))
    ydiff = 100 * (math.sin(radAng))
    newX = center[0] + xdiff
    newY = center[1] + ydiff
    plots.append((newX, newY, 30))

for plot in plots:
    print("%s," % (plot,))
