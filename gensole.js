
var lfcr = '\r\n';


var GENSOLE = {};


// Models

var needsRender = true;  // render flag - checked by animation loop

var printer = {
    bedW: 295,
    bedD: 200
}

var Patient = function() {
    this.name = '';
    this.bodyWeight = 0;
    this.activityLevel = 'walking';
}
var patient = new Patient();

var Insock = function() {
    this.l = 260;
    this.hr = 40;
    this.tr = 40;
    this.iw = 50;
    this.il = 180;
    this.ow = 50;
    this.ol = 180;
    this.io = 35;
    this.oo = 39;
    this.whichFoot = 'Left';
    this.dox = 0;
    this.doy = 0;
    this.dr = 0;
    this.t = 25;
    this.tt = 3;
    this.archHeight = 25;
    this.archOffsetY = 130;
    this.archSupport = true;
    this.chamferHeight = 6;
    this.draftAngle = 0;
    this.showConstructionCurves = false;
    this.renderMode = 'glass';
    this.showDimensions = true;
    this.modifierZOffset = 0.56;  // applied to top/bottom of modifier
    this.modifierZMax = 5;  // default to 5mm thick
    this.calcContour = false;
    this.hideModifiers = false;
    this.showUpperSurface = false;
    this.relaxIterations = 20;
    this.triangleSize = 2;

    this.overrideDensities = function(){
        if (modifiers.length > 0) {
            modifiers.map(function(m) {
                m.density = m.calculatedDensity;
            });
            this.thicknessChanged = true;
            reactToChanges();
        }

    };
}
var insock = new Insock();
var insockMesh;
var insockShape;
var insockText;


var footScan = {
    x: 5,
    y:-11,
    z:0,
    xr:-1,
    yr:0,
    zr:1,
    numPlanes: 3,
    planeStart:0.5,
    planeOffset:5,
    hideFoot:false
};


// global model updated by DAT.GUI
var uiModel = {
    l:  260,
    hr: 40,  // heel radius
    tr: 40,  // toe radius
    iw: 50,  // instep width
    il: 180, // instep length
    ow: 50,  // outstep width
    ol: 180, // outstep length
    io: 35,  // instep offset - defines concavity of instep
    oo: 39,  // outstep offset - defines concavity of outstep
    whichFoot: 'Left',
    dox: 0,  // DXF offset in x
    doy: 0,  // DXF offset in y
    dr: 0,   // DXF rotation
    t: 25,  // thickness of heel
    tt: 3,  // thickness of toe
    archHeight: 25,  // height of arch control point
    archOffsetY: 130,  // y offset of arch control point
    draftAngle: 0,
    chamferHeight: 6,
    renderMode: 'glass',
    showDimensions: true,
    modifierZOffset: 0.56,  // applied to top/bottom of modifier
    modifierZMax: 5,
    calcContour: false,
    hideModifiers: false,
    showUpperSurface: false,
    relaxIterations: 20,
    triangleSize: 2,
    x: 5,
    y:-11,
    z:0,
    xr:-1,
    yr:0,
    zr:1,
    numPlanes: 3,
    planeStart:0.5,
    planeOffset:5,
    hideFoot:false
};


// Modifiers
// Array of modifiers
var modifiers = [];
var modifierMode = 'none';


// THREE.js objects
var amfCamera, amfCameraOrt, amfScene, amfRenderer, amfControls, transformControl;
var amfProfile, amfDXF, amfDims, amfDims2,
    amfFoot, amfFootIntersections,
    amfDragControls, amfDimControls,
    dirLight, dirLight2, gPlane,
    amfAxes, stats;

var cameraMode = true;  // true = perspective, false = othographic
var activeCamera = null;

var turntableEnabled = false;

var footObj, bakedFootGeo;

var raycaster = new THREE.Raycaster();
var mouse = new THREE.Vector2(),
    dragOffset = new THREE.Vector3(),
    INTERSECTED, SELECTED, HOVERING;

var dragPlane;

/*
    Prompt shortcut...
    TODO: Move this into library
*/
function prompt2(title, defaultValue, callback) {
    var box = bootbox.prompt({
      title: title,
      value: defaultValue,
      callback: callback
    });
    box.bind('shown.bs.modal', function () {
    	box.find("input").select();
    });
}



/*
    Generation Sequencing
*/

var genQueue = {
    from:0,
    to:Infinity
};

var genFlags = {
    kill:false,
    complete:true,
    pending:false, // set true when a fresh attempt to regen is queued, but not started
    queued:false,
    completedStage:-1,
    from:0,
    to:Infinity
};

var regenWorker = new Worker('js/app/worker.js');
regenWorker.sendCmd = function(cmd, msg, cb) {
    this.callback = cb;
    this.postMessage({
        cmd: cmd,
        msg:msg
    });
}
regenWorker.addEventListener('message', function(e) {
    if (this.callback)
        this.callback(e.data);
});


var genStages = {
    calcProfile: 0,
    buildProfile: 1,
    buildDims:2,
    buildProfileMesh:3,
    refineInsockMesh:4,
    updateSurfaceContour:5,
    calcFootIntersections:6,
    relaxSurfaceContour:7
};


function updateProgressBar(err) {
    var v = genFlags.tasksDone / genFlags.numTasks;
    $('#progress .bar').html(err).width((v*100) + '%');
}

var regenCount = 0;
function regen(from, to) {


    from = from || 0;
    to = to || Infinity;

    //console.log('Regen:', from, to, genFlags);

    if (genFlags.pending) {
        if (to > genFlags.to || from < genFlags.from) {
            genQueue.to = Math.max(to, genFlags.to);
            genQueue.from = Math.min(from, genFlags.from);
            genFlags.queued = true;
            //console.log('Queued:', genQueue.from, genQueue.to);
        }
        return;
    }

    regenCount++;

    genFlags.pending = true;
    genFlags.from = Math.min(from, genFlags.from);
    from = genFlags.from;
    genFlags.to = to;
    //console.log('from: ', genFlags.from);

    // build task list
    var tasks = { };
    genFlags.numTasks = 0;

    var last = undefined;

    function prepTask(name, fn) {
        var tmp = [];
        if (last)
            tmp.push(last);
        tmp.push(fn);
        last = name;
        tasks[name] = tmp;
        genFlags.numTasks++;
    }

    if (from <= genStages.calcProfile && genStages.calcProfile <= to) {
        prepTask('calcProfile',function(cb, res) {
            updateProgressBar(null);
            setTimeout(function() {
                needsRender=true;
                if (!genFlags.kill) {
                    var err = GENSOLE.Insock.recalc(insock);
                    err = err ? null : new Error("invalid profile: " + err);
                    if (!err) genFlags.completedStage = genStages.calcProfile;
                    genFlags.tasksDone++;
                    cb(err, null);

                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }

            },0);
        });
    }

    if (from <= genStages.buildProfile && genStages.buildProfile <= to) {
        prepTask('buildProfile', function(cb, res) {
            updateProgressBar(null);
            setTimeout(function() {
                needsRender=true;
                if (!genFlags.kill) {
                    updateDragControls();
                    var err = rebuildProfile();
                    err = err ? null : new Error("error building profile: " + err);
                    if (!err) genFlags.completedStage = genStages.buildProfile;
                    genFlags.tasksDone++;
                    cb(err, null)
                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }
            },0);
        });
    }

    if (from <= genStages.buildDims && genStages.buildDims <= to) {
        prepTask('buildDims', function(cb, res) {
            updateProgressBar(null);
            setTimeout(function() {
                needsRender=true;
                if (!genFlags.kill) {
                    rebuildDims();
                    genFlags.completedStage = genStages.buildDims;
                    genFlags.tasksDone++;
                    cb(null, null)
                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }
            },0);
        });
    }

    if (from <= genStages.buildProfileMesh && genStages.buildProfileMesh <= to) {
        prepTask('buildProfileMesh', function(cb, res) {
            updateProgressBar(null);
            setTimeout(function() {
                needsRender=true;
                if (!genFlags.kill) {
                    rebuildProfileMesh(function() {
                        genFlags.tasksDone++;
                        genFlags.completedStage = genStages.buildProfileMesh;
                        cb(null, null);
                    });
                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }
            },0);
        });
    }

    /*
    if (from <= genStages.refineInsockMesh && genStages.refineInsockMesh <= to) {

        //reset
        genFlags.refineInsockMeshIterationsDone = 0;

        prepTask('refineInsockMesh', function(cb, res) {
            updateProgressBar(null);
            var tf = function(cb) {
                // check we've not been killed
                if (!genFlags.kill) {
                    // do some processing
                    if (refineInsockMesh()) {
                        genFlags.tasksDone++;
                        cb(null,null);
                    } else
                        setTimeout(function() { tf(cb) },0);  // needs another iteration
                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }
            };
            setTimeout(function() { tf(cb) }, 0);
        });
    }
    */

    if (from <= genStages.updateSurfaceContour && genStages.updateSurfaceContour <= to) {
        prepTask('updateSurfaceContour', function(cb, res) {
            updateProgressBar(null);
            setTimeout(function() {
                needsRender=true;
                if (!genFlags.kill) {
                    var err = updateSurfaceContour() ? null : new Error("error contouring surface");
                    if (!err) genFlags.completedStage = genStages.updateSurfaceContour;
                    genFlags.tasksDone++;
                    cb(err, null)
                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }
            },0);
        });
    }

    if (from <= genStages.calcFootIntersections && genStages.calcFootIntersections <= to) {
        prepTask('calcFootIntersections', function(cb, res) {
            updateProgressBar(null);
            setTimeout(function() {
                needsRender=true;
                if (!genFlags.kill) {
                    var err = calcFootIntersections() ? null : new Error("error calculating intersections");
                    if (!err) genFlags.completedStage = genStages.calcFootIntersections;
                    genFlags.tasksDone++;
                    cb(err, null);
                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }

            },0);
        });
    }


    if (from <= genStages.relaxSurfaceContour && genStages.relaxSurfaceContour <= to) {

        //reset
        genFlags.relaxInterationsDone = 0;

        prepTask('relaxSurfaceContour', function(cb, res) {
            updateProgressBar(null);
            var tf = function(cb) {
                // check we've not been killed
                if (!genFlags.kill) {
                    // do some processing
                    if (relaxSurfaceContour()) {
                        genFlags.tasksDone++;
                        genFlags.completedStage = genStages.relaxSurfaceContour;
                        cb(null,null);
                    } else
                        setTimeout(function() { tf(cb) },0);  // needs another iteration
                } else {
                    genFlags.tasksDone++;
                    cb(null,null);
                }
            };
            setTimeout(function() { tf(cb) }, 0);
        });
    }


    // kill anything running
    genFlags.kill = !genFlags.complete;
    //if (genFlags.kill) regenWorker.sendCmd('cancel', null, null);

    //console.log('a',genFlags);

    // wait for running tasks to complete
    async.whilst(
        function () { return !genFlags.complete },
        function (callback) {
            setTimeout(callback, 10);
        },
        function (err) {
            // ready to regen
            genFlags.pending = false;
            genFlags.tasksDone = 0;

            if (from > genFlags.completedStage+1) {
                regen(genFlags.completedStage+1, to);
            } else {
                //console.log('Starting regen:',regenCount, from, to, genFlags);
                genFlags.complete = false;
                if (to == Infinity)
                    genFlags.needsRegen = false;
                $('#progress').stop().show().removeClass('ok error');
                updateProgressBar(null);
                async.auto(
                    tasks
                    ,
                    function(err, results) {
                        if (err) {
                            $('#progress').addClass('error');
                        } else {
                            $('#progress').fadeOut('slow');
                        }

                        //console.log('Regen complete', genFlags.kill);

                        genFlags.tasksDone = genFlags.numTasks;
                        updateProgressBar(err);
                        needsRender = true;
                        genFlags.kill = false;
                        genFlags.complete = true;

                        // anything queued?
                        if (genFlags.queued) {
                            genFlags.queued = false;
                            regen(genQueue.from, genQueue.to);
                        }
                    }
                );
            }

            regenCount--;
        }
    );

}


/*
    UI objects
*/

var gui, guif3, guif4, guiFPatient;

var uiFSM = StateMachine.create({
    initial: 'none',
    events: [
        { name: 'left',  from: 'patient',  to: 'profile' },
        { name: 'right',  from: 'patient',  to: 'profile' },
        { name: 'toPatient',  from: ['none','profile','modifiers','soleMorph'],  to: 'patient' },
        { name: 'toProfile',  from: ['patient','modifiers','soleMorph'],  to: 'profile' },
        { name: 'toSoleMorph',  from: ['patient','profile','modifiers'],  to: 'soleMorph' },
        { name: 'toModifiers',  from: ['patient','profile','soleMorph'],  to: 'modifiers' },
    ],
    callbacks: {
        onleft:  function(event, from, to) {
            insock.whichFoot = 'Left';
            updatePatientInfo();
            $('#rootwizard').bootstrapWizard('show',1);
        },
        onright:  function(event, from, to) {
            insock.whichFoot = 'Right';
            updatePatientInfo();
            $('#rootwizard').bootstrapWizard('show',1);
        },
        ontoModifiers:  function(event, from, to) {
            $('#rootwizard').bootstrapWizard('show',3);
        },
        ontoPatient:  function(event, from, to) {
            $('#rootwizard').bootstrapWizard('show',0);
        },
        ontoProfile:  function(event, from, to) {
            $('#rootwizard').bootstrapWizard('show',1);
        },
        ontoSoleMorph:  function(event, from, to) {
            $('#rootwizard').bootstrapWizard('show',2);
        },

        onpatient: function() {

            amfDims.visible = false;
            amfDims2.visible = false;
            amfDimControls.visible = false;
            amfAxes.visible = false;

            if (!gui.closed) gui.closed = true;
            $('#infoPanel').fadeOut();
        },
        onprofile: function() {
            guif3.close();

            amfDims.visible = true;
            amfDimControls.visible = true;
            amfProfile.visible = true;
            amfAxes.visible = true;

            //if (gui.closed) gui.closed = false;
            $('#infoPanel').fadeOut();
        },

        onsoleMorph: function() {

            if (modifierMode == 'none' || modifierMode == 'stl') guif3.open();

            amfDims.visible = false;
            amfDimControls.visible = false;
            amfDims2.visible = false;
            amfDXF.visible = true;
            amfAxes.visible = true;
            amfProfile.visible = true;
            amfDims2.visible = modifierMode == 'stl';

            if (gui.closed) gui.closed = false;
            $('#infoPanel').fadeOut();
        },

        onmodifiers: function() {

            if (modifierMode == 'none' || modifierMode == 'stl') guif3.open();

            amfDims.visible = false;
            amfDimControls.visible = false;
            amfDims2.visible = false;
            amfDXF.visible = true;
            amfAxes.visible = true;
            amfProfile.visible = true;
            amfDims2.visible = modifierMode == 'stl';

            if (gui.closed) gui.closed = false;
            if (modifiers.length > 0) $('#infoPanel').fadeIn();
        },



        onenterstate: function() {
            needsRender = true;
            updateDragControls();
        },
    }
});


function updateGUI() {
    if (gui && gui.__folders)
        for (var j in gui.__folders) {
            for (var i in gui.__folders[j].__controllers) {
                gui.__folders[j].__controllers[i].updateDisplay();
            }
        }

    if (insock.archSupport) {
        $('#archSupportBut').prop('checked',true);
        $('#archSupportBut').parent().removeClass('off');
    } else {
        $('#archSupportBut').prop('checked',false);
        $('#archSupportBut').parent().addClass('off')
    }

    if (insock.calcContour) {
        $('#soleMorphBut').prop('checked',true);
        $('#soleMorphBut').parent().removeClass('off');
    } else {
        $('#soleMorphBut').prop('checked',false);
        $('#soleMorphBut').parent().addClass('off')
    }

    updateDragControls();
    updateDimControls();
}




function resetModifiers() {
    modifiers = [];

    // reset group
    while (amfDXF.children.length > 0) {
        var tmp = amfDXF.children[0];
        amfDXF.remove(tmp);
        tmp.geometry.dispose();
        tmp.material.dispose();
    }

    // remove foot scan intersections
    while (amfFootIntersections.children.length > 0) {
        var tmp = amfFootIntersections.children[0];
        amfFootIntersections.remove(tmp);
        tmp.geometry.dispose();
        tmp.material.dispose();
    }

    $('#infoPanel').html('').hide();
}


function resetFootScan() {
    // empty foot scan objects
    while (amfFoot.children.length > 0) {
        tmp = amfFoot.children[0];
        amfFoot.remove(tmp);
        tmp.geometry.dispose();
        tmp.material.dispose();
    }

    footObj = null;

    resetModifiers();
}


/*
    Draggable controls
*/

function addDragControl(updateFn, dragFn, normal) {
    var object = new THREE.Mesh(
        amfDragControls.sharedGeo,
        new THREE.MeshLambertMaterial( {
            color: 0x880000,
            transparent:true,
            opacity:0.5
        } )
    );
    object.update = updateFn;
    object.drag = dragFn;
    object.normal = normal;
    amfDragControls.add(object);
}

function initDragControls() {
    amfDragControls = new THREE.Group();
    amfScene.add(amfDragControls);

    // shared geometry
    amfDragControls.sharedGeo = new THREE.SphereGeometry( 2 );

    // drag objects

    // outside width and length
    addDragControl(
        function() {
            this.position.set((insock.whichFoot == 'Left' ? -1 : 1)*insock.ow, insock.ol, 0);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var ow = clamp(Math.abs(p.x), insock.tr+1, 100);
            var ol = clamp(p.y, insock.l * 0.55, insock.l - ow-1);

            if (ow != insock.ow || ol != insock.ol) {
                insock.ow = ow;
                insock.ol = ol;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(0,0,1)
    );

    // inside width and length
    addDragControl(
        function() {
            this.position.set((insock.whichFoot == 'Left' ? 1 : -1)*insock.iw, insock.il, 0);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var iw = clamp(Math.abs(p.x), insock.tr+1, 100);
            var il = clamp(p.y, insock.l * 0.6, insock.l - iw-1);

            if (iw != insock.iw || il != insock.il) {
                insock.iw = iw;
                insock.il = il;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(0,0,1)
    );

    // length
    addDragControl(
        function() {
            this.position.set(0, insock.l, 0);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var l = clamp(Math.abs(p.y), insock.tr + insock.hr, 500);

            if (l != insock.l) {
                insock.l = l;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(0,0,1)
    );

    // heel
    addDragControl(
        function() {
            this.position.set(0, 0, insock.t);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var v = clamp(p.z, 1, 100);

            if (v != insock.t) {
                insock.t = v;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(1,0,0)
    );

    // toe
    addDragControl(
        function() {
            this.position.set(0, insock.l, insock.tt);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var v = clamp(p.z, 1, 100);

            if (v != insock.tt) {
                insock.tt = v;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(1,0,0)
    );

    // modifier z max
    addDragControl(
        function() {
            this.position.set(0, 0, insock.modifierZMax);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var v = clamp(p.z, 1, Math.max(insock.t, insock.tt, insock.archHeight));

            if (v != insock.modifierZMax) {
                insock.modifierZMax = v;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(1,0,0)
    );

    // modifier z max
    addDragControl(
        function() {
            this.position.set(0, 0, insock.chamferHeight);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var v = clamp(p.z, 1, Math.max(insock.t, insock.tt));

            if (v != insock.chamferHeight) {
                insock.chamferHeight = v;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(1,0,0)
    );

    // instep offset
    addDragControl(
        function() {
            this.position.set((insock.whichFoot == 'Left' ? 1 : -1)*insock.io, insock.h + insock.hr, 0);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var io = clamp(Math.abs(p.x), 1, insock.hr-1);

            if (io != insock.io) {
                insock.io = io;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(0,0,1)
    );

    // outstep offset
    addDragControl(
        function() {
            this.position.set((insock.whichFoot == 'Left' ? -1 : 1)*insock.oo, insock.ho + insock.hr, 0);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var oo = clamp(Math.abs(p.x), 1, insock.ow);

            if (oo != insock.oo) {
                insock.oo = oo;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(0,0,1)
    );

    // toe radius
    addDragControl(
        function() {
            this.position.set((insock.whichFoot == 'Left' ? 1 : -1)*insock.tr, insock.l - insock.tr, 0);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var tr = clamp(Math.abs(p.x), 10, Math.min(insock.iw, insock.ow));

            if (tr != insock.tr) {
                insock.tr = tr;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(0,0,1)
    );

    // heel radius
    addDragControl(
        function() {
            this.position.set((insock.whichFoot == 'Left' ? 1 : -1)*insock.hr, insock.hr, 0);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var hr = clamp(Math.abs(p.x), 10, Math.min(insock.iw, insock.ow));

            if (hr != insock.hr) {
                insock.hr = hr;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(0,0,1)
    );

    // arch position
    addDragControl(
        function() {
            this.position.set((insock.whichFoot == 'Left' ? 1 : -1)*insock.iw,
            insock.archOffsetY,
            insock.archHeight);
            this.visible = uiFSM.current == 'profile';
        },
        function(p) {

            var y = clamp(p.y, 1, insock.l);
            var z = clamp(p.z, 1, 100);

            if (y != insock.archOffsetY || z != insock.archHeight) {
                insock.archOffsetY = y;
                insock.archHeight = z;
                this.update();
                regen(0, genStages.buildProfile);
                genFlags.needsRegen = true;
            }
        },
        new THREE.Vector3(1,0,0)
    );
}

function updateDragControls() {
    amfDragControls.children.map(function(c) {
        if (c.update) c.update();
    });
}




/*
    Dimension controls
*/

function addDimControl(updateFn, clickFn, normal) {

    var g = new THREE.Group();

    g.x1 = 0;
    g.y1 = 0;
    g.x2 = 10;
    g.y2 = 0;
    g.z1 = 0;
    g.z2 = 0;
    g.x3 = undefined;
    g.y3 = undefined;
    g.x4 = undefined;
    g.y4 = undefined;
    g.txt = '';

    g.normal = normal;
    g.click = clickFn;

    g.update = function() {
        updateFn(g);

        // update internal objects
        g.text.geometry.dispose();
        g.text.geometry = new THREE.TextGeometry(g.txt, {
            font: 'helvetiker',
            size: 4,
            height:0,
            curveSegments: 2
        });

        var x = (g.x1 + g.x2)/2;
        var y = (g.y1 + g.y2)/2;

        var angle = Math.atan2(g.y2-g.y1, g.x2-g.x1);
        if (angle){
            if (angle > Math.PI/2 ) angle -= Math.PI;
            if (angle < -Math.PI/2 ) angle += Math.PI;
        }

        // center?
        var dx = 0, dy = 0;
        g.text.geometry.computeBoundingBox();
        var bb = g.text.geometry.boundingBox;
        var offset1 = -bb.max.x/2;
        var offset2 = 2;
        dx = offset1 * Math.cos(angle) + offset2 * Math.cos(angle + Math.PI/2);
        dy = offset1 * Math.sin(angle) + offset2 * Math.sin(angle + Math.PI/2);

        // rotate?
        if (angle && angle != 0) {
            g.text.rotation.z = angle;
        }

        g.text.position.x = x + dx;
        g.text.position.y = y + dy;


        // update hittest
        g.hittest.geometry.vertices[1].x = bb.max.x;
        g.hittest.geometry.vertices[2].x = bb.max.x;
        g.hittest.geometry.vertices[2].y = bb.max.y;
        g.hittest.geometry.vertices[3].y = bb.max.y;
        g.hittest.geometry.verticesNeedUpdate = true;
        g.hittest.geometry.computeBoundingSphere();

        g.hittest.position.x = x + dx;
        g.hittest.position.y = y + dy;
        g.hittest.rotation.z = angle;


        // update dim line
        g.dimLine.geometry.verticesNeedUpdate = true;
        g.dimLine.geometry.vertices[0].set(g.x1,g.y1,g.z1);
        g.dimLine.geometry.vertices[1].set(g.x2,g.y2,g.z2);

        // update leader 1
        if (g.x3 !== undefined) {
            g.leader1.geometry.verticesNeedUpdate = true;
            g.leader1.geometry.vertices[0].set(g.x1,g.y1,g.z1);
            g.leader1.geometry.vertices[1].set(g.x3,g.y3,g.z1);
            g.leader1.visible = true;
        }

        // update leader 2
        if (g.x4 !== undefined) {
            g.leader2.geometry.verticesNeedUpdate = true;
            g.leader2.geometry.vertices[0].set(g.x2,g.y2,g.z2);
            g.leader2.geometry.vertices[1].set(g.x4,g.y4,g.z2);
            g.leader2.visible = true;
        }
    };



    var c = 0x808080;

    // Dim line
    g.dimLine = MakeLine(g.x1,g.y1,g.x2,g.y2, c);
    g.add(g.dimLine);

    // leader 1
    g.leader1 = MakeLine(g.x1,g.y1,0,0, c);
    g.leader1.visble=false;
    g.add(g.leader1);

    // leader 2
    g.leader2 = MakeLine(g.x2,g.y2,0,0, c);
    g.leader2.visble=false;
    g.add(g.leader2);

    // text
    g.text = MakeText(g.txt, 0, 0, true, 0);
    g.add(g.text);

    // hittest
    var hitgeo = new THREE.Geometry();
    hitgeo.vertices.push(new THREE.Vector3(0,0,0));
    hitgeo.vertices.push(new THREE.Vector3(10,0,0));
    hitgeo.vertices.push(new THREE.Vector3(10,10,0));
    hitgeo.vertices.push(new THREE.Vector3(0,10,0));
    hitgeo.faces.push(new THREE.Face3(0,1,2, normal, c, 0));
    hitgeo.faces.push(new THREE.Face3(0,2,3, normal, c, 0));
    hitgeo.dynamic = true;

    g.hittest = new THREE.Mesh(
        hitgeo,
        new THREE.MeshLambertMaterial( {
            side: THREE.DoubleSide,
            color:0x000000,
            transparent:true,
            opacity:0.3
        } )
    );
    g.hittest.visible = false;
    g.hittest.g = g;
    g.add(g.hittest);

    amfDimControls.add(g);

    // prepare a list of objects to test for intersections

    amfDimControls.intersectAgainst.push(g.hittest);
}


function initDimControls() {
    amfDimControls = new THREE.Group();
    amfScene.add(amfDimControls);

    amfDimControls.intersectAgainst = [];


    // length
    addDimControl(
        function(g) {
            g.txt = 'Length: '+insock.l.toFixed(0);
            g.x1 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.iw+25);
            g.y1 = 0;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.iw+25);
            g.y2 = insock.l;
            g.x4 = 0;
            g.y4 = g.y2;
        },
        function(g) {
            prompt2("Length:", insock.l.toFixed(0), function(v) {
                if (v) {
                    insock.l = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );


    // inside width
    addDimControl(
        function(g) {
            g.txt = 'Inside Width: '+insock.iw.toFixed(0);
            g.y1 = insock.il;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.iw);
            g.y2 = insock.il;
        },
        function(g) {
            prompt2("Inside Width:", insock.iw.toFixed(0), function(v) {
                if (v) {
                    insock.iw = parseFloat(v);
                    updateDimControls();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // outside width
    addDimControl(
        function(g) {
            g.txt = 'Outside Width: '+insock.ow.toFixed(0);
            g.y1 = insock.ol;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (-insock.ow);
            g.y2 = insock.ol;
        },
        function(g) {
            prompt2("Outside Width:", insock.ow.toFixed(0), function(v) {
                if (v) {
                    insock.ow = parseFloat(v);
                    updateDimControls();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // inside length
    addDimControl(
        function(g) {
            g.txt = 'Inside Length: '+insock.il.toFixed(0);
            g.x1 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.iw + 5);
            g.y1 = 0;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.iw + 5);
            g.y2 = insock.il;
            g.x4 = 0;
            g.y4 = insock.il;
        },
        function(g) {
            prompt2("Inside Length:", insock.il.toFixed(0), function(v) {
                if (v) {
                    insock.il = parseFloat(v);
                    updateDimControls();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // outside length
    addDimControl(
        function(g) {
            g.txt = 'Outside Length: '+insock.ol.toFixed(0);
            g.x1 = (insock.whichFoot == 'Left' ? 1 : -1) * (-insock.ow - 5);
            g.y1 = 0;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (-insock.ow - 5);
            g.y2 = insock.ol;
            g.x4 = 0;
            g.y4 = insock.ol;
        },
        function(g) {
            prompt2("Outside Length:", insock.ol.toFixed(0), function(v) {
                if (v) {
                    insock.ol = parseFloat(v);
                    updateDimControls();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );


    // instep offset
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Instep Offset: '+insock.io.toFixed(0);
            g.x1 = 0;
            g.y1 = insock.h + insock.hr;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.io);
            g.y2 = insock.h + insock.hr;
        },
        function(g) {
            prompt2("Instep Offset:", insock.io.toFixed(0), function(v) {
                if (v) {
                    insock.io = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // outstep offset
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Outstep Offset: '+insock.oo.toFixed(0);
            g.x1 = 0;
            g.y1 = insock.ho + insock.hr;
            g.x2 = (insock.whichFoot == 'Left' ? -1 : 1) * (insock.oo);
            g.y2 = insock.ho + insock.hr;
        },
        function(g) {
            prompt2("Outstep Offset:", insock.oo.toFixed(0), function(v) {
                if (v) {
                    insock.oo = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // toe radius
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Toe Radius: '+insock.tr.toFixed(0);
            g.x1 = 0;
            g.y1 = insock.l - insock.tr;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.tr);
            g.y2 = insock.l - insock.tr;
        },
        function(g) {
            prompt2("Toe Radius:", insock.tr.toFixed(0), function(v) {
                if (v) {
                    insock.tr = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );


    // heel radius
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Heel Radius: '+insock.hr.toFixed(0);
            g.x1 = 0;
            g.y1 = insock.hr;
            g.x2 = (insock.whichFoot == 'Left' ? 1 : -1) * (insock.hr);
            g.y2 = insock.hr;
        },
        function(g) {
            prompt2("Heel Radius:", insock.hr.toFixed(0), function(v) {
                if (v) {
                    insock.hr = parseFloat(v);
                    if (insock.io > insock.hr - 1)
                        insock.io = insock.hr - 1;
                    updateDimControls();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );


    // toe thickness
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Toe Thickness: '+insock.tt.toFixed(0);
            g.x1 = 0;
            g.y1 = insock.tt;
            g.x2 = 50;
            g.y2 = insock.tt;
            g.x3 = 0;
            g.y3 = insock.tt;
            g.rotation.x = Math.PI/2;
            g.rotation.y = Math.PI/2;
            g.position.y = insock.l;
        },
        function(g) {
            prompt2("Toe Thickness:", insock.tt.toFixed(0), function(v) {
                if (v) {
                    insock.tt = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // heel thickness
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Heel Thickness: '+insock.t.toFixed(0);
            g.x1 = -50;
            g.y1 = insock.t;
            g.x2 = 0;
            g.y2 = insock.t;
            g.x4 = 0;
            g.y4 = insock.t;
            g.rotation.x = Math.PI/2;
            g.rotation.y = Math.PI/2;
        },
        function(g) {
            prompt2("Heel Thickness:", insock.t.toFixed(0), function(v) {
                if (v) {
                    insock.t = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // modifier Z Max thickness
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Variable Density Thickness: '+insock.modifierZMax.toFixed(0);
            g.x1 = -85;
            g.y1 = insock.modifierZMax;
            g.x2 = 0;
            g.y2 = insock.modifierZMax;
            g.x4 = 0;
            g.y4 = insock.modifierZMax;
            g.rotation.x = Math.PI/2;
            //g.rotation.y = Math.PI/2;
        },
        function(g) {
            prompt2("Variable Density Thickness:", insock.modifierZMax.toFixed(0), function(v) {
                if (v) {
                    insock.modifierZMax = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    // chamfer height
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            g.txt = 'Chamfer Height: '+insock.chamferHeight.toFixed(0);
            g.x1 = 0;
            g.y1 = insock.chamferHeight;
            g.x2 = 60;
            g.y2 = insock.chamferHeight;
            g.x4 = 0;
            g.y4 = insock.chamferHeight;
            g.rotation.x = Math.PI/2;
            //g.rotation.y = Math.PI/2;
        },
        function(g) {
            prompt2("Chamfer Height:", insock.chamferHeight.toFixed(0), function(v) {
                if (v) {
                    v = parseFloat(v);
                    v = clamp(v, 1, Math.max(insock.t, insock.tt));
                    insock.chamferHeight = v;
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );


    // draft angle
    addDimControl(
        function(g) {
            if (insock.status != 'valid' ) return;
            var offset = Math.max(10, insock.t/2);
            g.txt = 'Draft Angle: '+insock.draftAngle.toFixed(0) + String.fromCharCode(176);
            g.x1 = -50;
            g.y1 = insock.t - offset;
            g.x2 = -10;
            g.y2 = insock.t - offset;
            g.x4  = 0;
            g.y4 = 0;
            //g.rotation.x = Math.PI/2;
            //g.rotation.y = -Math.PI/2;

            g.rotation.z = Math.PI/2;
            if (offset > 10)
                g.rotation.y = Math.PI/2
            else
                g.rotation.y = 0;
        },
        function(g) {
            prompt2("Draft Angle (degrees):", insock.draftAngle.toFixed(0), function(v) {
                if (v) {
                    insock.draftAngle = parseFloat(v);
                    g.update();
                    regen();
                }
            });
        },
        new THREE.Vector3(0,0,1)
    );

    /*
    var dl = MakeDimLine(
            -50,
            insock.t,
            0,
            insock.t,
            "Heel Thickness: "+insock.t.toFixed(0),
            -50,
            insock.t,
            0,
            0
    );
    dl.g.rotation.x = Math.PI/2;
    amfDims.add(dl.g);
    */

}

function updateDimControls() {
    amfDimControls.children.map(function(c) {
        if (c.update) c.update();
    });
}



/*
    Profile construction
*/


function ArcByTwoPoints(shape, cx,cy,r,x1,y1,x2,y2, clockwise, segments) {

    segments = segments || 100;

    var ang1 = Math.atan2(y1-cy, x1-cx);
    var ang2 = Math.atan2(y2-cy, x2-cx);

    var signChange = false;

    // make sure ang2 is always bigger than ang1 (i.e. CCW)
    if (ang2 < ang1) {
        ang2 += 2*Math.PI;
    }

    // get the diff - works for CCW arcs
    var ang3 = ang2 - ang1;

    if (clockwise) {
        ang2 -= 2*Math.PI;
        ang3 = (ang2 - ang1);
    }

    for (var i=0; i < segments-1; i++) {
        var theta;

        theta = (i/(segments-1)) * ang3 + ang1;

        shape.lineTo(cx + r*Math.cos(theta),  cy + r*Math.sin(theta));
    }


}




function ArcPointsByTwoPoints(points, cx,cy,r,x1,y1,x2,y2, clockwise, segments) {

    segments = segments || 100;

    var ang1 = Math.atan2(y1-cy, x1-cx);
    var ang2 = Math.atan2(y2-cy, x2-cx);

    var signChange = false;

    // make sure ang2 is always bigger than ang1 (i.e. CCW)
    if (ang2 < ang1) {
        ang2 += 2*Math.PI;
    }

    // get the diff - works for CCW arcs
    var ang3 = ang2 - ang1;

    if (clockwise) {
        ang2 -= 2*Math.PI;
        ang3 = (ang2 - ang1);
    }

    eps = 0.001;

    for (var i=0; i < segments; i++) {
        var theta;

        theta = (i/(segments-1)) * ang3 + ang1;

        var x = cx + r*Math.cos(theta);
        var y = cy + r*Math.sin(theta);
        var p = new THREE.Vector2(x,y);
        if (points.length > 0) {
            var lp = points[points.length-1];
            if (lp.distanceToSquared(p) > eps)
                points.push(p);
        } else {
            points.push(p);
        }



    }
}



function LinePointsByTwoPoints(points, x1,y1, x2,y2, segments) {

    segments = segments || 100;

    eps = 0.001;

    var p1 = new THREE.Vector2(x1,y1);
    var p2 = new THREE.Vector2(x2,y2);


    for (var i=0; i < segments; i++) {
        var theta = (i/(segments-1));

        var p = p1.clone();
        p.lerp(p2, theta);

        if (points.length > 0) {
            var lp = points[points.length-1];
            if (lp.distanceToSquared(p) > eps)
                points.push(p);
        } else {
            points.push(p);
        }
    }
}


function calcProfileNormals(points, clockwise) {
    var normals = [];

    var lp = points[0];
    normals.push(new THREE.Vector2(0,1));
    for (var i=1; i<points.length; i++) {
        var p = points[i];
        var tan1 = p.clone();
        tan1.sub(lp);
        var tmp = tan1.x;
        if (clockwise) {
            tan1.x = -tan1.y;
            tan1.y = tmp;
        } else {
            tan1.x = tan1.y;
            tan1.y = -tmp;
        }

        tan1.normalize();
        normals.push(tan1);

        lp = p;
    }

    return normals;
}


function disposeObject(obj) {
    if (obj.type == 'Group') {
        obj.children.map(function(c) {
            disposeObject(c);
        })
    } else {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
    }
}


function transferableCopy(obj) {
    var tmp = {};
    for (var k in obj) {
        if (_.isArray(obj[k])) {

            tmp[k] = [];
            for (var i=0; i < obj[k].length; i++) {
                tmp[k].push(transferableCopy(obj[k][i]));
            }

        } else if (_.isObject(obj[k]) || _.isFunction(obj[k])) {

        } else {
            tmp[k] = obj[k];
        }
    }
    return tmp;
}


function rebuildProfile() {

    try {
        // assumes that the Insock calculations have already been done!
        console.time('rebuildProfile');


        // reset profile
        while (amfProfile.children.length > 0) {
            var tmp = amfProfile.children[0];
            amfProfile.remove(tmp);

            tmp.geometry.dispose();
            if (tmp != insockMesh) tmp.material.dispose();
        }


        /*
            Final Profile
        */

        // build inside and outside point sequences, from top to bottom
        var inPoints = [];
        var outPoints = [];
        var invert = insock.whichFoot == 'Right';

        // approx insock.l /

        var numSeg = clamp(Math.round(insock.l / 4 / insock.triangleSize),20,100);

        // inside toe arc
        ArcPointsByTwoPoints(
            inPoints,
            0,
            insock.l - insock.tr,
            insock.tr,
            0,
            insock.l,
            insock.ii1[0],
            insock.ii1[1],
            true,
            numSeg);

        // inside convex arc
        ArcPointsByTwoPoints(
            inPoints,
            insock.iw - insock.ir,
            insock.il,
            insock.ir,
            insock.ii1[0],
            insock.ii1[1],
            insock.ii2[0],
            insock.ii2[1],
            true,
            numSeg);

        // inside concave arc
        ArcPointsByTwoPoints(
            inPoints,
            insock.io + insock.r3,
            insock.hr + insock.h,
            insock.r3,
            insock.ii2[0],
            insock.ii2[1],
            insock.ii3[0],
            insock.ii3[1],
            false,
            numSeg
        );

        // inside heel
        ArcPointsByTwoPoints(
            inPoints,
            0,
            insock.hr,
            insock.hr,
            insock.ii3[0],
            insock.ii3[1],
            0,
            0,
            true,
            numSeg
        );



        // outside toe arc
        ArcPointsByTwoPoints(
            outPoints,
            0,
            insock.l - insock.tr,
            insock.tr,
            0,
            insock.l,
            insock.oi1[0],
            insock.oi1[1],
            false,
            numSeg);


        // outside convex arc
        ArcPointsByTwoPoints(
            outPoints,
            -insock.ow + insock.or,
            insock.ol,
            insock.or,
            insock.oi1[0],
            insock.oi1[1],
            insock.oi2[0],
            insock.oi2[1],
            false,
            numSeg
        );

        if (insock.outstepSolution == 'concave') {
            // outside concave arc
            ArcPointsByTwoPoints(
                outPoints,
                -insock.oo - insock.r4,
                insock.hr + insock.ho,
                insock.r4,
                insock.oi2[0],
                insock.oi2[1],
                insock.oi3[0],
                insock.oi3[1],
                true,
                numSeg
            );
        } else {
            LinePointsByTwoPoints(outPoints, insock.oi2[0], insock.oi2[1], insock.oi3[0], insock.oi3[1], numSeg);
        }

        // outside heel
        ArcPointsByTwoPoints(
            outPoints,
            0,
            insock.hr,
            insock.hr,
            insock.oi3[0],
            insock.oi3[1],
            0,
            0,
            false,
            numSeg
        );


        insock.inPoints = inPoints;
        insock.outPoints = outPoints;

        insock.inNormals = calcProfileNormals(inPoints, true);
        insock.outNormals = calcProfileNormals(outPoints, false);


        // match the heel normals
        insock.outNormals[insock.outNormals.length-1].set(0,-1);
        insock.inNormals[insock.inNormals.length-1].set(0,-1);


        // final validity checks
        //if (insock.inPoints.length != insock.outPoints.length) insock.status = 'invalid';



        // check to see if points have steadily decresing y values
        // if not, then they have degenerate curvature!
        if (insock.status == 'valid') {
            var ly1 = insock.inPoints[0].y,
                ly2 = insock.outPoints[0].y;

            for (var i=1; i < insock.inPoints.length; i++) {
                if (ly1 - insock.inPoints[i].y < 0 ||
                    ly2 - insock.outPoints[i].y < 0) {
                    insock.status = 'invalid';
                    break;
                }
                ly1 = insock.inPoints[i].y;
                ly2 = insock.outPoints[i].y;
            }
        }

        // outline
        if (insock.status == 'valid') {
            var lineGeo = new THREE.Geometry();
            inPoints.map(function(p) {
                lineGeo.vertices.push(new THREE.Vector3((invert ? -1 : 1)*p.x, p.y, 0));
            });
            var line = new THREE.Line( lineGeo, new THREE.LineBasicMaterial( { color: 0x4A6B1C, linewidth: 2 } ) );
            amfProfile.add( line );

            lineGeo = new THREE.Geometry();
            outPoints.map(function(p) {
                lineGeo.vertices.push(new THREE.Vector3((invert ? -1 : 1)*p.x, p.y, 0));
            });
            line = new THREE.Line( lineGeo, new THREE.LineBasicMaterial( { color: 0x4A6B1C, linewidth: 2 } ) );
            amfProfile.add( line );
        }


        console.timeEnd('rebuildProfile');

        return insock.status == 'valid';
    } catch(err) {
        console.error('rebuildProfile - caught error: ', err);
        console.error('insock object: ', insock);

        return insock.status == 'invalid';
    }
}


function rebuildDims() {
    // reset dims
    while (amfDims.children.length > 0) {
        var tmp = amfDims.children[0];
        amfDims.remove(tmp);
        disposeObject(tmp);
    }


    /*
        Construction Curves
    */

    // heel
    amfProfile.add(MakeEllipseCurve(0, insock.hr, insock.hr, insock.hr, 0, 2*Math.PI, false ,50, 0xFF0000, true));

    // toe
    amfProfile.add(MakeEllipseCurve(0, insock.l-insock.tr, insock.tr, insock.tr, 0, 2*Math.PI, false ,50, 0xFF0000, true));


    //amfProfile.add(MakeLine(insock.oi2[0], insock.oi2[1], insock.oi3[0], insock.oi3[1], 0xFF0000));

    //amfProfile.add(MakeEllipseCurve(-insock.oo - insock.r4, insock.hr + insock.ho, insock.r4, insock.r4, 0, 2*Math.PI, false ,50, 0xFF0000, true));


    // inside concave
    //amfProfile.add(MakeEllipseCurve(insock.io + insock.r3, insock.hr + insock.h, insock.r3, insock.r3, 0, 2*Math.PI, false ,50, 0xFF0000, true));

    /*
        // outside convex
        amfProfile.add(MakeEllipseCurve(-insock.ow + insock.or, insock.ol, insock.or, insock.or, 0, 2*Math.PI, false ,50, 0xFF0000, true));

        // outside concave
        amfProfile.add(MakeEllipseCurve(-insock.hr - insock.otr, insock.hr, insock.otr, insock.otr, 0, 2*Math.PI, false ,50, 0xFF0000, true));


        // inside convex
        amfProfile.add(MakeEllipseCurve(insock.iw - insock.ir, insock.il, insock.ir, insock.ir, 0, 2*Math.PI, false ,50, 0xFF0000, true));

        // inside concave
        amfProfile.add(MakeEllipseCurve(insock.io + insock.r3, insock.hr + insock.h, insock.r3, insock.r3, 0, 2*Math.PI, false ,50, 0xFF0000, true));
    */

    /*
        Key Measurements
    */

    var invert = insock.whichFoot == 'Right';


    // upper surface for debugging

    if (insock.showUpperSurface) {
        var upperSurfaceWireframe = new THREE.Mesh(insock.upperSurface, new THREE.MeshLambertMaterial({
            color:0x000000,
            transparent:true,
            opacity:0.05,
            shading: THREE.FlatShading,
            wireframe:true
        }));
        amfDims.add(upperSurfaceWireframe);


        // upper surface control frame
        insock.upperSurfacePatch.buildControlFrame(amfDims);
    }
}



var footMaterialsCache = {};

function getInsockMaterial() {
    if (footMaterialsCache.vector === undefined) {
        footMaterialsCache.vector = new THREE.Vector3( 0, 0, -1 );
        footMaterialsCache.vector.applyQuaternion( activeCamera.quaternion );

        footMaterialsCache.glassMat = new THREE.ShaderMaterial({
    	    uniforms:
    		{
    			"c":   { type: "f", value: 1.0 },
    			"p":   { type: "f", value: 1.4 },
    			glowColor: { type: "c", value: new THREE.Color(0xFF9900) },
    			viewVector: { type: "v3", value: footMaterialsCache.vector }
    		},
    		vertexShader:   document.getElementById( 'vertexShader'   ).textContent,
    		fragmentShader: document.getElementById( 'fragmentShader' ).textContent,
    		side: THREE.FrontSide,
    		blending: THREE.NormalBlending,
    		transparent: true,
            shading: THREE.FlatShading
    	});


        footMaterialsCache.wireframeMat = new THREE.MeshNormalMaterial({
            wireframe:true,
            side:THREE.FrontSide
        });

        footMaterialsCache.solidMat = new THREE.MeshPhongMaterial({
            color:0xbfdb64,
            shading: THREE.FlatShading
        });
    }


    if (insock.renderMode == 'wireframe') {
        return footMaterialsCache.wireframeMat;
    } else if (insock.renderMode == 'solid') {
        return footMaterialsCache.solidMat;
    } else
        return footMaterialsCache.glassMat;
}


function rebuildProfileMesh(cb) {

    console.time('rebuildProfileMesh');

    var inPoints = insock.inPoints;
    var outPoints = insock.outPoints;

    var pl = inPoints.length;

    insock.extraIndex = 6*pl;
    //console.log(insock.extraIndex);

    // validity checks ??

    // rebuild mesh via worker
    regenWorker.sendCmd('updateInsock', transferableCopy(insock), function(data) {

        if (insock.status == 'valid') {
            regenWorker.sendCmd('generateProfileMesh', null, function(data) {

                var geo = new THREE.Geometry();
                geo.dynamic = true;

                // build geo object
                var v;
                for (var i=0; i<data.vertices.length; i++) {
                    v = new THREE.Vector3(data.vertices[i][0], data.vertices[i][1], data.vertices[i][2]);
                    v.orig = [v.x, v.y, v.z];
                    geo.vertices.push(v);
                }


                for (var i=0; i<data.faces.length; i++)
                    geo.faces.push(new THREE.Face3(data.faces[i][0], data.faces[i][1], data.faces[i][2]));

                // ready for rendering
                //geo.mergeVertices();
                geo.computeFaceNormals();

                mat = getInsockMaterial();
                var mesh = new THREE.Mesh( geo,mat);

                mesh.renderOrder = 150;


                insockMesh = mesh;
                insockMesh.receiveShadow=true;
                insockMesh.castShadow=true;

                amfProfile.add( mesh );

                needsRender=true;

                if (cb) cb();
            });
        } else {
            if (cb) cb();
        }

    });


    if (insockText) {
        amfScene.remove(insockText);
        insockText.geometry.dispose();
        insockText.material.dispose();
    }

    if (patient.name != '') {
        // text
        var textShape = new THREE.TextGeometry(patient.name.toUpperCase(), {
            font: 'helvetiker',
            size: 12,
            weight:'bold',
            height:insock.modifierZOffset,
            curveSegments: 3
        });
        var textMat = new THREE.MeshLambertMaterial({
            overdraw:true,
            color: new THREE.Color(colorByDensity(10/100)),
            shading: THREE.FlatShading,
            transparent:true,
            opacity:0.2
        });
        insockText = new THREE.Mesh(textShape, textMat);
        insockText.geometry.computeFaceNormals();

        // move to 2/3 up
        var wf = insock.whichFoot == 'Left' ? 1 : -1;
        insockText.geometry.computeBoundingBox();
        var bb = insockText.geometry.boundingBox;
        insockText.rotation.z = wf * Math.PI/2;   // rotate

        insockText.position.x = -wf * (bb.max.y + bb.min.y)/2;  // center y
        insockText.position.y = -wf * (bb.max.x + bb.min.x)/2;  // center x
        // flip
        insockText.rotation.y = Math.PI;
        insockText.position.z = insock.t-0.5; // move to right height
        insockText.position.y += insock.l * 0.4;  // move towards toe

        insockText.position.z = insock.modifierZOffset;

        // debug
        amfScene.add(insockText);
    }

    console.timeEnd('rebuildProfileMesh');

}

/*
function refineInsockMesh() {
    var tesselator = new THREE.TessellateModifier(insock.triangleSize*2, 0.5);


    var vl = insockMesh.geometry.vertices.length;

    var geo = tesselator.modify(insockMesh.geometry, true);
    insockMesh.geometry.dispose();
    insockMesh.geometry = geo;


    // update z positions
    var ray = new THREE.Ray(new THREE.Vector3(0, 0, 0), new THREE.Vector3(0,0,1));
    for (var i=vl; i<geo.vertices.length; i++)  {
        v = geo.vertices[i];

        // build a ray
        ray.origin.set(v.x, v.y, 0);

        // find intersection with upper surface
        for (var j=0; j<insock.upperSurface.faces.length; j++) {
            var f = insock.upperSurface.faces[j];
            var a = insock.upperSurface.vertices[f.a],
                b = insock.upperSurface.vertices[f.b],
                c = insock.upperSurface.vertices[f.c];

            var intersect = ray.intersectTriangle(a,b,c, false);
            if (intersect) {
                v.z = intersect.z;
                v.origZ = v.z;
                break;
            }
        };
    }

    needsRender=true;

    genFlags.refineInsockMeshIterationsDone++;
    return genFlags.refineInsockMeshIterationsDone > 20;
}
*/

function scaleShape(shape, scale, about) {
    // for each action
    shape.actions.map(function(a) {
        if (a.action == 'moveTo' || a.action == 'lineTo' ) {
            // scale args about
            a.args[0] = about[0] + (a.args[0] - about[0]) * scale[0];
            a.args[1] = about[1] + (a.args[1] - about[1]) * scale[1];

        } else {
            console.log(a);
        }
    });
}

function reverseShape(shape) {
    // reverse lineTo actions, leave moveTo alone
    // let's assume the first action is a moveTo
    // and reverse everything else
    shape.actions.reverse();
    // put the moveTo back at the beginning
    shape.actions.unshift(shape.actions.pop());
}

var amf = {};

// pass a density measure from 0 to 1
function colorByDensity(u) {

    // TODO: replace these with dynamic limits
    umin = 0.1;
    umax = 0.3;
    udif = umax - umin;

    u = clamp(u, umin, umax);

    // blend from pure yellow at umin to pure red at umax
    return new THREE.Color( 1, (umax-u)/(udif), 0 );
}


function buildAxes( ) {
    var axes = new THREE.Object3D();

    axes.add( buildAxis( new THREE.Vector3( 0, 0, 0 ), new THREE.Vector3( 100, 0, 0 ), 0xFF0000, false ) ); // +X
    axes.add( buildAxis( new THREE.Vector3( 0, 0, 0 ), new THREE.Vector3( -100, 0, 0 ), 0xFF0000, true) ); // -X
    axes.add( buildAxis( new THREE.Vector3( 0, 0, 0 ), new THREE.Vector3( 0, 500, 0 ), 0x9ffb00, false ) ); // +Y
    axes.add( buildAxis( new THREE.Vector3( 0, 0, 0 ), new THREE.Vector3( 0, -50, 0 ), 0x8feb00, true ) ); // -Y
    axes.add( buildAxis( new THREE.Vector3( 0, 0, 0 ), new THREE.Vector3( 0, 0, 30 ), 0x0000FF, false ) ); // +Z
    axes.add( buildAxis( new THREE.Vector3( 0, 0, 0 ), new THREE.Vector3( 0, 0, -50 ), 0x0000FF, true ) ); // -Z

    return axes;

}

function buildAxis( src, dst, colorHex, dashed ) {
    var geom = new THREE.Geometry(),
        mat;

    if(dashed) {
        mat = new THREE.LineDashedMaterial({ linewidth: 1, color: colorHex, dashSize: 3, gapSize: 3, transparent:true, opacity:0.5 });
    } else {
        mat = new THREE.LineBasicMaterial({ linewidth: 1, color: colorHex, transparent:true, opacity:0.7 });
    }

    geom.vertices.push( src.clone() );
    geom.vertices.push( dst.clone() );
    geom.computeLineDistances(); // This one is SUPER important, otherwise dashed lines will appear as simple plain lines

    var axis = new THREE.Line( geom, mat, THREE.LinePieces );

    return axis;

}


THREE.Vector3.prototype.toAMFString = function() {
    return "<vertex><coordinates>" + "<x>" + this.x.toFixed(5) + "</x><y>" + this.y.toFixed(5) + "</y><z>" + this.z.toFixed(5) + "</z>" + "</coordinates></vertex>\n";
};


function savePatientRecords(zip) {

    var record = {
        patient: patient,
        profile: insock,
        footScan:footScan,
        modifiers:[]
    }

    record.profile.modifierMode = modifierMode;

    // save insock profile as DXF
    fn = insock.whichFoot+'-Insole.dxf';
    if (patient.name != '') {
        fn = patient.name + '/' + fn;
    }
    var dxf = shapeToDXF(insockShape);
    if (zip) {
        zip.file(fn, dxf);
    } else
        $.ajax({
            url:"/library/save",
            method:'POST',
            cache: false,
            data: {
                name: fn,
                data: dxf
            },
            success:function( data ) {
                notify(data.message, data.status);
            },
            dataType:"json"
        });


    // save insock profile as STL
    fn = insock.whichFoot+'-Insole.stl';
    if (patient.name != '') {
        fn = patient.name + '/' + fn;
    }
    var stl = meshToSTL(insockMesh);
    if (zip) {
        zip.file(fn, stl);
    } else
        $.ajax({
            url:"/library/save",
            method:'POST',
            cache: false,
            data: {
                name: fn,
                data: stl
            },
            success:function( data ) {
                notify(data.message, data.status);
            },
            dataType:"json"
        });


    // save foot mesh as STL
    if (footObj) {
        amfFoot.updateMatrixWorld();

        fn = insock.whichFoot+'-Foot.stl';
        if (patient.name != '') {
            fn = patient.name + '/' + fn;
        }
        var stl = meshToSTL(footObj, true);
        if (zip) {
            zip.file(fn, stl);
        } else
            $.ajax({
                url:"/library/save",
                method:'POST',
                cache: false,
                data: {
                    name: fn,
                    data: stl
                },
                success:function( data ) {
                    notify(data.message, data.status);
                },
                dataType:"json"
            });
    }



    // save modifier curves
    if (modifiers.length > 0) {

        modifiers.map(function(m) {

            // check we're not just saving DXF curves back out again!
            //if (m.group.endsWith('dxf')) return;

            var dxf = shapeToDXF(m.shape);

            var fn2 = insock.whichFoot+'_'+m.group+'_'+m.part+'_'+m.density.toFixed(1)+'.dxf';
            if (patient.name != '') {
                fn2 = patient.name + '/' + fn2;
            }
            m.filenameDXF = fn2;

            if (zip) {
                zip.file(fn2, dxf);
            } else
                $.ajax({
                    url:"/library/save",
                    method:'POST',
                    cache: false,
                    data: {
                        name: fn2,
                        data: dxf
                    },
                    success:function( data ) {
                        notify(data.message, data.status);
                    },
                    dataType:"json"
                });

            // also save out the modifier as an STL
            fn2 = insock.whichFoot+'_'+m.group+'_'+m.part+'_'+m.density.toFixed(1)+'.stl';
            if (patient.name != '') {
                fn2 = patient.name + '/' + fn2;
            }
            m.filenameSTL = fn2;
            var stl = meshToSTL(m.mesh);
            if (zip) {
                zip.file(fn2, stl);
            } else
                $.ajax({
                    url:"/library/save",
                    method:'POST',
                    cache: false,
                    data: {
                        name: fn2,
                        data: stl
                    },
                    success:function( data ) {
                        notify(data.message, data.status);
                    },
                    dataType:"json"
                });

            // copy critical info to patient record
            record.modifiers.push({
                group:m.group,
                part:m.part,
                density:m.density,
                areamm2: m.areamm2,
                areacm2: m.areacm2,
                aream2: m.aream2,
                pressure: m.pressure,
                calculatedDensity: m.calculatedDensity,
                filenameDXF: m.filenameDXF,
                filenameSTL: m.filenameSTL
            });

        });
    }


    // save configuration info summary
    var fn = insock.whichFoot+'-Insole.json';
    if (patient.name != '') {
        fn = patient.name + '/' + fn;
    }
    if (zip) {
        zip.file(fn, JSON.stringify(record, null, '\t') );
    } else
        $.ajax({
            url:"/library/save",
            method:'POST',
            cache: false,
            data: {
                name: fn,
                data: JSON.stringify(record, null, '\t')
            },
            success:function( data ) {
                notify(data.message, data.status);
            },
            dataType:"json"
        });
}


function generateAMF() {

    // build a matrix to orient for printing
    var orient1 = new THREE.Matrix4();
    var orient2 = new THREE.Matrix4();

    var m1 = new THREE.Matrix4();
    var m2 = new THREE.Matrix4();
    var m3 = new THREE.Matrix4();

    var alpha = -Math.atan2(insock.t - insock.tt, insock.l);  // tilt to match surface
    var beta = Math.PI;  // flip over
    var gamma = Math.atan2(printer.bedW, printer.bedD);  // orient along longest diagonal of print bed

    /*
    if (!insock.calcContour) {
        m1.makeRotationX( alpha );
        m2.makeRotationY( beta );
    }
    */
    m3.makeRotationZ( gamma );

    orient1.multiplyMatrices( m1, m2 );
    orient2.multiply(m3);


    // populate AMF object from whatever we have in memory
    amf = {
        name:insock.whichFoot+'-Insole',
        geo: insockMesh.geometry,
        "metadata": {
            "slic3r.extruder":0,
            "slic3r.fill_pattern":"rectilinear"
        },
        "modifiers": []
    };

    // populate modifiers
    modifiers.map(function(m, index) {
        m.mesh.updateMatrixWorld();
        amf.modifiers.push({
            "metadata": {
                "slic3r.extruder":0,
                "slic3r.fill_density": m.density + "%",
                "slic3r.fill_pattern":"honeycomb"
            },
            group:m.group,
            part:m.part,
            mesh:m.mesh,
            geo: m.mesh.geometry
        });
    });

    // sort by density, ascending
    amf.modifiers.sort(function(a, b){return a.metadata['slic3r.fill_density']-b.metadata['slic3r.fill_density']});


    var result = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<amf unit=\"millimeter\">\n";
    result += '<metadata type="cad">r 1.2.9</metadata>\n';
    result += "<object id=\"0\">\n";
    result += '<metadata type="name">'+amf.name+'</metadata>\n';
    if (amf.metadata) Object.keys(amf.metadata).map(function(m) {
        result += '<metadata type="'+m+'">'+amf.metadata[m]+'</metadata>\n';
    });
    result += "<mesh>\n";

    // first we dump all vertices
    result += "<vertices>\n";

    // part
    amf.geo.vertices.map(function(p) {
        result += p.clone().applyMatrix4(orient1).applyMatrix4(orient2).toAMFString();
    });

    // for each modifier
    amf.modifiers.map(function(m) {
        m.geo.vertices.map(function(v) {
            result += v.clone().applyMatrix4(m.mesh.matrixWorld).applyMatrix4(orient1).applyMatrix4(orient2).toAMFString();
        });
    });

    // for the text
    if (insockText) {
        insockText.updateMatrixWorld();
        insockText.geometry.vertices.map(function(v) {
            result += v.clone().applyMatrix4(insockText.matrixWorld).applyMatrix4(orient1).applyMatrix4(orient2).toAMFString();
        });
    }

    result += "</vertices>\n";


    // then we dump all faces

    // first for the primary volume
    var n = 0;
    result += "<volume>\n";

    result += '<metadata type="name">'+amf.name+'</metadata>\n';
    if (amf.metadata) Object.keys(amf.metadata).map(function(m) {
        result += '<metadata type="'+m+'">'+amf.metadata[m]+'</metadata>\n';
    });

    amf.geo.faces.map(function(p) {

        result += "<triangle>";
        result += "<v1>" + (p.a) + "</v1>";
        result += "<v2>" + (p.b) + "</v2>";
        result += "<v3>" + (p.c) + "</v3>";
        result += "</triangle>\n";

    });
    result += "</volume>\n";

    n += amf.geo.vertices.length;

    // then for the modifier meshes
    var mid = 1;
    amf.modifiers.map(function(m, index) {
        result += "<volume>\n";

        result +=  '<metadata type="name">'+m.group + '-' + m.part +'</metadata>\n'+
                   '<metadata type="slic3r.modifier">1</metadata>\n';

       if (m.metadata) Object.keys(m.metadata).map(function(mkey) {
           result += '<metadata type="'+mkey+'">'+m.metadata[mkey]+'</metadata>\n';
       });

        m.geo.faces.map(function(p) {

            result += "<triangle>";
            result += "<v1>" + (p.a + n) + "</v1>";
            result += "<v2>" + (p.b + n) + "</v2>";
            result += "<v3>" + (p.c + n) + "</v3>";
            result += "</triangle>\n";

        });
        result += "</volume>\n";

        n += m.geo.vertices.length;
        mid ++;
    });

    // then for the text
    if (insockText) {
        result += "<volume>\n";

        result +=  '<metadata type="name">MagicText</metadata>\n';
        result += '<metadata type="slic3r.modifier">1</metadata>\n';
        result += '<metadata type="slic3r.perimeters">5</metadata>\n';


        insockText.geometry.faces.map(function(p) {

            result += "<triangle>";
            result += "<v1>" + (p.a + n) + "</v1>";
            result += "<v2>" + (p.b + n) + "</v2>";
            result += "<v3>" + (p.c + n) + "</v3>";
            result += "</triangle>\n";

        });
        result += "</volume>\n";
    }

    result += "</mesh>\n";
    result += "</object>\n";

    result += "</amf>\n";
    return result;
}


function sliceAMF(zip) {

    updateSurfaceContourOfModifiers();
    needsRender =true;

    savePatientRecords(zip);

    var result = generateAMF();

    // Save back to server
    var fn = amf.name + '.amf';
    if (patient.name != '') {
        fn = patient.name + '/' + fn;
    }

    if (zip) {
        zip.file(fn, result);
    } else
        $.ajax({
            url:"/library/save",
            method:'POST',
            cache: false,
            data: {name: fn, data: result},
            success:function( data ) {
                notify(data.message, data.status);

                // open in r
                $.ajax({
                    url:"/slic3r",
                    method:'POST',
                    cache: false,
                    //data: {command: 'slic3r --gui library/'+fn+' --load Slic3r_Variable_Density_config_bundle.ini --gui-mode export', async:true},
                    data: {filename: fn, async:true},
                    success:function( data ) {
                        notify(data.message, data.status);
                    },
                    dataType:"json"
                });
            },
            dataType:"json"
        });
}

function downloadZip() {
    var zip = new JSZip();

    sliceAMF(zip);

    var fn = insock.whichFoot + '.zip';
    if (patient.name != '') {
        fn = patient.name + '-' + fn;
    }

    try {
        var blob = zip.generate({type:"blob"});
        saveAs(blob, fn);
    } catch(e) {
        // aargh
        notify(e.message, 'error');
    }
}


var downloadData = (function () {
    var a = document.createElement("a");
    document.body.appendChild(a);
    a.style = "display: none";
    return function (data, fileName) {
        var blob = new Blob([data], {type: "octet/stream"}),
            url = window.URL.createObjectURL(blob);
        a.href = url;
        a.download = fileName;
        a.target = '_blank';
        a.click();

        setTimeout(function() { window.URL.revokeObjectURL(url); }, 30000);
    };
}());


function downloadAMF() {
    updateSurfaceContourOfModifiers();
    needsRender = true;

    var data = generateAMF();
    downloadData(data, 'insole.amf');
}


function render() {
    if (amfControls.autoRotate && amfControls.autoRotateSpeed < 2) {
        amfControls.autoRotateSpeed += 0.001;
        amfControls.autoRotate = turntableEnabled;
    }
    amfControls.update();
    if (needsRender && amfRenderer) {
        stats.begin();

        var tmp = insock.renderMode == 'solid';
        if (tmp != amfRenderer.shadowMapEnabled) {
            amfRenderer.shadowMapEnabled = tmp;
            gPlane.material.needsUpdate = true;
        }

        if (modifierMode == 'stl') {
            amfFootIntersections.visible = !insock.hideModifiers;
        } else if (modifierMode == 'dxf') {
            amfDXF.visible = !insock.hideModifiers;
        }

        if (footObj && modifierMode == 'stl') {
            footObj.visible = !footScan.hideFoot;
            transformControl.visible = footObj.visible && uiFSM.current == 'soleMorph';

            //axes
            transformControl.enableAxis.X = true;
            transformControl.enableAxis.Y = true;
            transformControl.enableAxis.Z = true;
            transformControl.enableAxis.E = true;

            // planes
            transformControl.enableAxis.XY = true;
            transformControl.enableAxis.YZ = true;
            transformControl.enableAxis.XZ = true;
            transformControl.enableAxis.XYZE = true;

        } else if (modifierMode == 'dxf') {
            transformControl.visible = amfDXF.visible && uiFSM.current == 'modifiers';

            //axes
            transformControl.enableAxis.X = transformControl.getMode() == 'translate';
            transformControl.enableAxis.Y = transformControl.enableAxis.X;
            transformControl.enableAxis.Z = transformControl.getMode() == 'rotate';
            transformControl.enableAxis.E = transformControl.enableAxis.X;

            // planes
            transformControl.enableAxis.XY = true;
            transformControl.enableAxis.YZ = false;
            transformControl.enableAxis.XZ = false;
            transformControl.enableAxis.XYZE = false;
        } else
        {
            transformControl.visible = false;
        }
        transformControl.enabled = transformControl.visible;


        if (insockMesh && insockMesh.material && insockMesh.material.uniforms) {
            insockMesh.material.uniforms.viewVector.value =
    		     new THREE.Vector3().subVectors( activeCamera.position, insockMesh.position );
        }

        transformControl.update();

        amfRenderer.render( amfScene, activeCamera );
        needsRender = false;

        // memory leak debugging
        //console.log(amfRenderer.info.memory);

        stats.end();
    }


    // queue up the next render
    requestAnimationFrame( render );
}

function init() {

    // setup renderer
    amfScene = new THREE.Scene();

    amfCamera = new THREE.PerspectiveCamera( 45, window.innerWidth/window.innerHeight, 1, 10000 );
    amfCamera.position.z = 450;
    amfCamera.position.x = 0;
    amfCamera.position.y = 100;
    amfCamera.up.set( 0, 0, 1 );
    amfScene.add( amfCamera );
    activeCamera = amfCamera;

    amfCameraOrt = new THREE.OrthographicCamera(window.innerWidth / - 2, window.innerWidth / 2, window.innerHeight / 2, window.innerHeight / - 2, 1, 1000 );
    amfCameraOrt.position.copy(amfCamera.position);
    amfCameraOrt.up.set( 0, 0, 1 );
    amfScene.add( amfCameraOrt );

    amfRenderer = new THREE.WebGLRenderer({ antialias: true }); //new THREE.CanvasRenderer();
    amfRenderer.setSize( window.innerWidth, window.innerHeight );
    amfRenderer.setClearColor( 0xffffff, 1);
    amfRenderer.shadowMapEnabled = true;
    amfRenderer.shadowMapSoft = true;
    //amfRenderer.shadowMapCullFrontFaces = false;

    amfControls = new THREE.OrbitControls( amfCamera, amfRenderer.domElement );
    amfControls.damping = 0.2;
    amfControls.target = new THREE.Vector3(0,130,0);
    amfControls.addEventListener( 'change', function() {
        needsRender=true;
    } );


    dirLight = new THREE.DirectionalLight( 0xffffff );
    dirLight.position.set(200, 400, 200);
    dirLight.castShadow =true;
    dirLight.shadowWidth = 512;
    dirLight.shadowHeight=512;
    dirLight.shadowDarkness = 0.2;
    dirLight.shadowBias = -0.005;
    var d = 200;
    dirLight.shadowCameraLeft = -d;
    dirLight.shadowCameraRight = d;
    dirLight.shadowCameraTop = d;
    dirLight.shadowCameraBottom = -d;
    dirLight.shadowCameraFar = 600;
    dirLight.target.position.y=130;
    amfScene.add( dirLight );
    amfScene.add(dirLight.target);

    dirLight2 = new THREE.DirectionalLight( 0x606060 );
    dirLight2.position.set(-50, -200, 300);
    dirLight2.castShadow =true;
    dirLight2.shadowDarkness = 0.2;
    dirLight2.shadowBias = -0.005;
    dirLight2.shadowCameraLeft = -d;
    dirLight2.shadowCameraRight = d;
    dirLight2.shadowCameraTop = d;
    dirLight2.shadowCameraBottom = -d;
    dirLight2.shadowCameraFar = 600;
    dirLight2.target.position.y=130;
    amfScene.add(dirLight2);
    amfScene.add(dirLight2.target);

    var light = new THREE.AmbientLight( 0x404040 ); // soft white light
    amfScene.add( light );

    amfAxes = buildAxes( 300 );
    amfAxes.visible = false;
    amfScene.add( amfAxes );

    amfProfile = new THREE.Group();
    amfScene.add(amfProfile);

    amfDXF = new THREE.Group();
    amfScene.add(amfDXF);

    amfDims = new THREE.Group();
    amfScene.add(amfDims);

    amfDims2 = new THREE.Group();
    amfScene.add(amfDims2);

    amfFoot = new THREE.Group();
    amfScene.add(amfFoot);

    // ground plane
    gPlane = new THREE.Mesh(
        new THREE.PlaneBufferGeometry(400,600),
        new THREE.MeshBasicMaterial({
            color:0xffffff,
            shading: THREE.FlatShading
        })
    );
    gPlane.position.z = -0.5;
    gPlane.position.y = 130;
    gPlane.receiveShadow =true;
    amfScene.add(gPlane);

    transformControl = new THREE.TransformControls( amfCamera, amfRenderer.domElement );
    transformControl.setSize(0.5);
    transformControl.addEventListener( 'change', function() {
        needsRender= true;
    });
    transformControl.addEventListener( 'objectChange', function() {
        transformControl.needsUpdate = true;
    } );
    transformControl.addEventListener( 'mouseUp', function() {
        if (transformControl.needsUpdate) {
            if (modifierMode == 'stl') {
                // update footScan properties
                footScan.x = transformControl.object.position.x;
                footScan.y = transformControl.object.position.y;
                footScan.z = transformControl.object.position.z;
                footScan.xr = radToDeg(transformControl.object.rotation.x);
                footScan.yr = radToDeg(transformControl.object.rotation.y);
                footScan.zr = radToDeg(transformControl.object.rotation.z);

                updateGUI();
                transformControl.needsUpdate = false;

                regen(genStages.updateSurfaceContour);
            } else if (modifierMode == 'dxf') {

                // update insock properties
                // TODO:
                insock.dox = transformControl.object.position.x;
                insock.doy = transformControl.object.position.y;
                insock.dr = radToDeg(transformControl.object.rotation.z);

                // no need to regen, as modifier extrusion/meshing happens at Slice time

                updateGUI();
                transformControl.needsUpdate = false;
            }

        }
    } );

    // leave detached for now...
    //transformControl.attach(amfFoot);
    amfScene.add(transformControl);

    amfFootIntersections = new THREE.Group();
    amfScene.add(amfFootIntersections);

    initDragControls();

    initDimControls();

    // drag plane
    dragPlane = new THREE.Mesh(
        new THREE.PlaneBufferGeometry( 2000, 2000, 8, 8 ),
        new THREE.MeshBasicMaterial( {
            color: 0x000000,
            opacity: 0.25,
            transparent: true,
            side: THREE.DoubleSide
        } )
    );
    dragPlane.visible = false;
    dragPlane.defNormal = new THREE.Vector3(0,0,1);
    amfScene.add(dragPlane);

    amfRenderer.shadowMapCullFace = THREE.CullFaceBack;

    $('#amfRenderer').append( amfRenderer.domElement );

    amfRenderer.domElement.addEventListener( 'mousemove', onDocumentMouseMove, false );
    amfRenderer.domElement.addEventListener( 'mousedown', onDocumentMouseDown, false );
    amfRenderer.domElement.addEventListener( 'mouseup', onDocumentMouseUp, false );
    window.addEventListener( 'resize', onWindowResize, false );

    amfControls.update();
}

function onWindowResize(){

    amfCamera.aspect = window.innerWidth / window.innerHeight;
    amfCamera.updateProjectionMatrix();

    amfCameraOrt.aspect = window.innerWidth / window.innerHeight;
    amfCameraOrt.updateProjectionMatrix();

    amfRenderer.setSize( window.innerWidth, window.innerHeight );

    needsRender = true;
}


var autoRotateTimer;

function onDocumentMouseMove( event ) {

    event.preventDefault();

    mouse.x = ( event.clientX / window.innerWidth ) * 2 - 1;
    mouse.y = - ( event.clientY / window.innerHeight ) * 2 + 1;

    //

    raycaster.setFromCamera( mouse, activeCamera );

    if ( SELECTED ) {

    	var intersects = raycaster.intersectObject( dragPlane );
        if (intersects.length> 0 && SELECTED.drag) {
            SELECTED.drag( intersects[ 0 ].point.sub( dragOffset ) );
        }

    	return;

    }

    var intersects = raycaster.intersectObjects( amfDragControls.children );

    if ( intersects.length > 0 ) {

    	if ( INTERSECTED != intersects[ 0 ].object ) {

    		if ( INTERSECTED ) {
                INTERSECTED.material.color.setHex( INTERSECTED.currentHex );
                INTERSECTED.material.opacity = 0.5;
            }

    		INTERSECTED = intersects[ 0 ].object;
    		INTERSECTED.currentHex = INTERSECTED.material.color.getHex();
            INTERSECTED.material.color.setHex(0xFF0000);
            INTERSECTED.material.opacity = 1;

    		dragPlane.position.copy( INTERSECTED.position );
            dragPlane.quaternion.setFromUnitVectors(dragPlane.defNormal, INTERSECTED.normal);
    		//plane.lookAt( camera.position );
            needsRender=true;
    	}

    } else {

    	if ( INTERSECTED ) {
            INTERSECTED.material.color.setHex( INTERSECTED.currentHex );
            INTERSECTED.material.opacity = 0.5;
            needsRender=true;
        }

    	INTERSECTED = null;

        // see if we're intersecting a dimension object

        intersects = raycaster.intersectObjects( amfDimControls.intersectAgainst );

        if (HOVERING) {
            if (HOVERING.g) {
                HOVERING.g.text.material.color.setHex( HOVERING.currentHex );
            } else {
                HOVERING.material.color.setHex( HOVERING.currentHex );
            }
            needsRender=true;
            HOVERING = null;
        }

        if ( intersects.length > 0 ) {
            HOVERING = intersects[ 0 ].object;
            HOVERING.currentHex = HOVERING.g.text.material.color.getHex();
            HOVERING.g.text.material.color.setHex(0xFF0000);
            needsRender=true;

        } else if (!insock.hideModifiers) {

            // test each modifier zone
            // TODO: do this better
            test = [];
            modifiers.map(function(m) {
                m.mesh.modi = m;
                test.push(m.mesh);
            });

            intersects = raycaster.intersectObjects( test );

            if ( intersects.length > 0 ) {

                HOVERING = intersects[ 0 ].object;
                HOVERING.currentHex = HOVERING.material.color.getHex();
                HOVERING.material.color.setHex(0x00FF00);
                needsRender=true;

                updateModifierInfo(HOVERING.modi);
            } else {
                updateModifierInfo();
            }


        }
    }
}

function onDocumentMouseDown( event ) {

    event.preventDefault();

    if (autoRotateTimer) {
        clearTimeout(autoRotateTimer);
        amfControls.autoRotate=false;
    }

    if (event.button && event.button > 1) return;

    var picked = false;

    //var vector = new THREE.Vector3( mouse.x, mouse.y, 0.5 ).unproject( activeCamera );

    //var raycaster = new THREE.Raycaster( activeCamera.position, vector.sub( activeCamera.position ).normalize() );

    mouse.x = ( event.clientX / window.innerWidth ) * 2 - 1;
    mouse.y = - ( event.clientY / window.innerHeight ) * 2 + 1;
    raycaster.setFromCamera( mouse, activeCamera );

    var intersects = raycaster.intersectObjects( amfDragControls.children );

    if ( intersects.length > 0 ) {

        amfControls.enabled = false;

        if (intersects[0].object.visible) {
            SELECTED = intersects[ 0 ].object;
            picked = true;

            var intersects = raycaster.intersectObject( dragPlane );
            if (intersects.length > 0)
               dragOffset.copy( intersects[ 0 ].point ).sub( dragPlane.position );
        }
    }

    if (!picked && amfDimControls.visible) {

        // see if we're intersecting a dimension object
        intersects = raycaster.intersectObjects( amfDimControls.intersectAgainst );

        if ( intersects.length > 0 ) {
            amfControls.enabled = false;
            picked =  true;

            intersects[0].object.g.click(intersects[0].object.g);

        }
    }

    if (!picked && !insock.hideModifiers) {
        // test each modifier zone
        // TODO: do this better
        test = [];
        modifiers.map(function(m) {
            m.mesh.modi = m;
            test.push(m.mesh);
        });

        intersects = raycaster.intersectObjects( test );

        if ( intersects.length > 0 ) {
            amfControls.enabled = false;
            picked = true;

            var modi = intersects[0].object.modi;

            // prompt
            // handle clicks
            prompt2("Density:", modi.density.toFixed(1), function(v) {
                if (v) {
                    modi.density = parseFloat(v);

                    modi.mesh.material.color.set(colorByDensity(modi.density/100));
                    modi.mesh.currentHex = modi.mesh.material.color.getHex();
                    needsRender=true;
                    updateModifierInfo(modi);
                }
            });
        }

    }

}

function onDocumentMouseUp( event ) {
    event.preventDefault();

    amfControls.enabled = true;

    if ( INTERSECTED ) {

    	dragPlane.position.copy( INTERSECTED.position );

    	SELECTED = null;

    }

    if (genFlags.needsRegen) {
        updateDimControls();
        regen(genStages.buildDims);
    }

    // start orbit timer
    if (turntableEnabled)
        autoRotateTimer = setTimeout(function() {
            amfControls.autoRotate=true;
            amfControls.autoRotateSpeed = 0;
        },5000);
}


// first two points define where dimension line starts and ends
// 3rd and 4th points define where leader lines extend to
function MakeDimLine(x1,y1,x2,y2,txt,x3,y3,x4,y4) {
    var c = 0x808080;
    var g = new THREE.Group();

    // Dim line
    g.add( MakeLine(x1,y1,x2,y2, c) );

    // leader 1
    if (x3 != undefined) g.add( MakeLine(x1,y1,x3,y3, c) );

    // leader 2
    if (x4 != undefined) g.add( MakeLine(x2,y2,x4,y4, c) );

    // text
    var text = MakeText(txt, (x1+x2)/2, (y1+y2)/2, true, Math.atan2(y2-y1, x2-x1));
    text.normal = new THREE.Vector3(0,0,1);
    g.add(text);

    return {g:g, t:text};
}

function MakeLine(x1,y1,x2,y2, c, lw) {
    var geo = new THREE.Geometry();
    geo.vertices.push(new THREE.Vector3(x1,y1,0));
    geo.vertices.push(new THREE.Vector3(x2,y2,0));
    return new THREE.Line( geo, new THREE.LineBasicMaterial( { color: c, linewidth: lw ? lw : 0.5 } ), THREE.LinePieces );
}


function MakeLine3(v1, v2, c, lw) {
    var geo = new THREE.Geometry();
    geo.vertices.push(v1);
    geo.vertices.push(v2);
    return new THREE.Line( geo, new THREE.LineBasicMaterial( { color: c, linewidth: lw ? lw : 0.5 } ), THREE.LinePieces );
}


function MakeText(text, x,y, center, angle, clr, size) {

    clr = clr ? clr : 0x707070;
    size = size ? size : 4;

    var shape = new THREE.TextGeometry(text, {
        font: 'helvetiker',
        size: size,
        height:0,
        curveSegments: 2
    });
    var mat = new THREE.MeshLambertMaterial({
        overdraw:true,
        color: clr,
        shading: THREE.FlatShading
    });
    var mesh = new THREE.Mesh(shape, mat);

    if (angle){
        if (angle > Math.PI/2 ) angle -= Math.PI;
        if (angle < -Math.PI/2 ) angle += Math.PI;
    }

    // center?
    var dx = 0, dy = 0;
    if (center) {
        mesh.geometry.computeBoundingBox();
        var offset1 = -mesh.geometry.boundingBox.max.x/2;
        var offset2 = 2;
        dx = offset1 * Math.cos(angle) + offset2 * Math.cos(angle + Math.PI/2);
        dy = offset1 * Math.sin(angle) + offset2 * Math.sin(angle + Math.PI/2);
    }

    // rotate?
    if (angle && angle != 0) {
        mesh.rotation.z = angle;
    }

    mesh.position.x = x + dx;
    mesh.position.y = y + dy;
    return mesh;
}


function MakeEllipseCurve(ax,ay,xr,yr,sa,ea,clockwise,numPoints, hexColor, dashed) {
    var curve = new THREE.EllipseCurve(
    	ax,  ay,            // ax, aY
    	xr, yr,           // xRadius, yRadius
    	sa,  ea,  // aStartAngle, aEndAngle
        clockwise             // aClockwise
    );

    var path = new THREE.Path( curve.getPoints( numPoints ) );
    var geometry = path.createPointsGeometry( numPoints );
    geometry.computeLineDistances();
    var material;
    if(dashed || true) {
        material = new THREE.LineDashedMaterial({ linewidth: 1, color: hexColor, dashSize:3, gapSize:3, transparent:true, opacity:0.3 });
    } else {
        material = new THREE.LineBasicMaterial({ linewidth: 1, color: hexColor, transparent:true, opacity:1 });
    }

    // Create the final Object3d to add to the scene
    return new THREE.Line( geometry, material );
}



function addModifier(groupName, part, density, shape, flatGeo, g, planeIndex) {
    var modifier = {
        group: groupName,
        part:part,
        density: density,
        shape:shape,
        flatGeo:flatGeo,
        mesh:null,
        areamm2:0,
        areacm2:0,
        aream2:0,
        pressure:0,
        g:g,
        planeIndex:planeIndex ? planeIndex : 0
    };

    modifiers.push(modifier);
}




function loadDXF(filename, fileText) {
    var density = 10;

    // attempt to parse density from filename
    var re = /((\d+)(.(\d)+)?).dxf/i;
    var found = re.exec(filename);
    if (found && found[1]) {
        density = parseFloat(found[1]);
        density = clamp(density, 0, 100);
    }

    parseDXF(filename, fileText, density);
}


function parseDXF(filename, fileText, density) {
    var clr = colorByDensity(density/100);

    var parser = new DxfParser();
    try {
        console.log('parsing: '+filename);

        var dxf = parser.parseSync(fileText);

        console.log('dxf parsed');

        // do something with the dxf
        if (dxf.entities && dxf.entities.length > 0) {
            dxf.entities.map(function(e, index) {
                if (e.type == 'LWPOLYLINE') {

                    var shape = new THREE.Shape();

                    shape.moveTo(e.vertices[0].x, e.vertices[0].y);
                    for (var j=1; j < e.vertices.length; j++) {
                        shape.lineTo(e.vertices[j].x, e.vertices[j].y);
                    }

                    var points = shape.createPointsGeometry();
                    var line = new THREE.Line( points, new THREE.LineBasicMaterial( { color: 0x4A6B1C, linewidth: 2, transparent:true, opacity:1 } ) );
                    amfDXF.add( line );

                    var flatGeo = new THREE.ShapeGeometry(shape);
                    flatGeo.mergeVertices();

                    addModifier(filename, index, density, shape, flatGeo, amfDXF);

                    needsRender = true;
                } else {
                    //console.log('Unknown entity',e);
                }
            })
        }


    }catch(err) {
        console.log(err.stack);
    }
}


function resetDXFGroup() {
    amfDXF.position.set(0,0,0);
    amfDXF.rotation.z = 0;
}

function updateDXFGroup() {
    amfDXF.position.x = insock.dox;
    amfDXF.position.y = insock.doy;
    amfDXF.rotation.z = Math.PI * insock.dr / 180;

    amfDXF.updateMatrixWorld();

    if (modifierMode == 'dxf') transformControl.attach(amfDXF);
}

function updateDXFGroupAndRender() {
    updateDXFGroup();
    needsRender = true;
}



// reader queue
var fileReaderQueue = [];
var fileReaderReady = true;
var fileReader = new FileReader();

fileReader.onload = function(e) {
    loadDXF(fileReader.filename, fileReader.result);

    fileReaderReady = true;
};

function readFiles() {
    if (fileReaderQueue.length > 0) {
        if (fileReaderReady) {
            fileReaderReady = false;

            var f = fileReaderQueue.pop();
            fileReader.filename = f.name;
            fileReader.readAsText( f );
        }

        setTimeout(function() {
            readFiles();
        }, 10);
    } else {
        // when finished
        updateDXFGroup();
        extrudeModifiers();
        //updateModifierInfo();
        needsRender = true;
    }
}


function updateProfileFromObject(shoe) {
    if (!shoe) return;

    // copy values into insock
    insock.l = shoe.l ? shoe.l : insock.l;
    insock.tr = shoe.tr ? shoe.tr : insock.tr;
    insock.hr = shoe.hr ? shoe.hr : insock.hr;
    insock.iw = shoe.iw ? shoe.iw : insock.iw;
    insock.il = shoe.il ? shoe.il : insock.il;
    insock.ow = shoe.ow ? shoe.ow : insock.ow;
    insock.ol = shoe.ol ? shoe.ol : insock.ol;
    insock.io = shoe.io ? shoe.io : insock.io;
    insock.oo = shoe.oo ? shoe.oo : insock.oo;

    // rebuild
    reactToChanges();

    // update gui
    updateGUI();
}


var shoeLibrary = [];
function initShoeLibrary() {
    //$('#shoeSelect').children().remove();

    $.ajax({
        url:"/library/shoes.json",
        method:'GET',
        cache: false,
        success:function( data ) {
            shoeLibrary = data;

            data.map(function(s,index) {
                $('#shoeSelect').append('<option value="'+index+'">' + s.brand + ' - '+ s.style  + ' - ' + s.euroSize +'</option>');
            });
        },
        dataType:"json"
    });


    // event handler
    $('#shoeSelect').on('change', function(v) {
        // get value
        var id = parseInt($('#shoeSelect').val());

        var shoe = shoeLibrary[id];

        updateProfileFromObject(shoe);
    });

    // alternate handler, for loading a shoe template from a json file
    var fileInput = document.getElementById('loadShoe');
    fileInput.addEventListener('change', function (event) {

        var fileUploader = this;
        var files = event.target.files;
        if (files.length > 0) {
            var file = files[0];
            if (file.name.endsWith('json')) {
                var reader = new FileReader();
                reader.onload = function(e) {
                    try {
                        var j = JSON.parse(reader.result);

                        // does the file have a profile object:
                        if (j.profile) j = j.profile;

                        updateProfileFromObject(j);

                        notify('Profile loaded', 'success');

                    } catch(e) {
                        notify('Error parsing shoe template: ' + e.message, 'error')
                    }
                }
                reader.readAsText(file);

            }
        }

        // reset file loader
        $('#loadShoe').val('');
    });
}


function fileInDir(d, f) {
    var found = false;
    d.children.map(function(f2) {
        if (f2.name == f) found=true;
    });
    return found;
}


var patientLibrary = [];
var selectedPatient = null;
function initPatientLibrary() {
    //$('#shoeSelect').children().remove();

    $.ajax({
        url:"/library/list",
        method:'GET',
        cache: false,
        success:function( data ) {

            // parse directories
            data.children.map(function(d, index) {
                if (d.type == 'directory') {
                    $('#patientSelect').append('<option value="'+index+'">' + d.name + '</option>');

                    // load patient info and add to patient library
                    var newP = {
                        id: index,
                        name: d.name,
                        bodyWeight:70,
                        left: null,
                        right: null
                    };

                    // see if there's a left?
                    var fn = 'Left-Insock.json';
                    if (fileInDir(d, fn))
                        $.ajax({
                            url: 'library/' + d.name + '/' + fn,
                            method:'GET',
                            cache: false,
                            success:function( data ) {
                                newP.left = data;
                                newP.bodyWeight = data.patient.bodyWeight;
                            },
                            dataType:"json"
                        });

                    // or a right?
                    fn = 'Right-Insock.json';
                    if (fileInDir(d, fn))
                        $.ajax({
                            url: 'library/' + d.name + '/' + fn,
                            method:'GET',
                            cache: false,
                            success:function( data ) {
                                newP.right = data;
                                newP.bodyWeight = data.patient.bodyWeight;
                            },
                            dataType:"json"
                        });

                    patientLibrary.push(newP);
                }
            });

        },
        dataType:"json"
    });




    // event handler
    $('#patientSelect').on('change', function(v) {
        // get value
        var id = $('#patientSelect').val();

        // find matching patient record
        var p = null;
        patientLibrary.map(function(pp) {
            if (pp.id == id) p = pp;
        });

        selectPatient(p);

    });
}

function selectPatient(p) {
    if (!p) return;

    selectedPatient = p;

    // update GUI fields
    $('#patientName').val(selectedPatient.name);
    $('#bodyWeight').val(selectedPatient.bodyWeight.toFixed(2));

    // update left/right buttons
    $('#leftBut').removeClass('btn-primary btn-default');
    $('#rightBut').removeClass('btn-primary btn-default');

    $('#leftBut').addClass(selectedPatient.left ? 'btn-primary' : 'btn-default');

    $('#rightBut').addClass(selectedPatient.right ? 'btn-primary' : 'btn-default');
}

function downloadShoeProfile() {
    var blob = new Blob([JSON.stringify(insock)], {type: "application/json"});
    saveAs(blob, 'shoe.json');
}

function initPatientLoader() {
    var fileInput = document.getElementById('loadProject');
    fileInput.addEventListener('change', function (event) {

        var fileUploader = this;
        var files = event.target.files;
        if (files.length > 0) {
            var file = files[0];
            if (file.name.endsWith('zip')) {
                var reader = new FileReader();
                reader.onload = function(e) {
                    try {
                        var zip = new JSZip(e.target.result);

                        var dir = '';
                        var json = {};

                        $.each(zip.files, function (index, zipEntry) {
                            if (zipEntry.name.endsWith('json')) {
                                json = JSON.parse(zipEntry.asText());
                                dir = zipEntry.name.split('/').shift() + '/';
                            }
                        });

                        if (json) {
                            // restructure json to match patient structure
                            json.name = json.patient.name;
                            json.bodyWeight = json.patient.bodyWeight;
                            json.zip = zip;
                            json.zipDir = dir;

                            if (json.profile.whichFoot == 'Left') {
                                json.left = {
                                    profile: json.profile,
                                    footScan: json.footScan,
                                    modifiers: json.modifiers
                                };
                            }

                            if (json.profile.whichFoot == 'Right') {
                                json.right = {
                                    profile: json.profile,
                                    footScan: json.footScan,
                                    modifiers: json.modifiers
                                };
                            }

                            selectPatient(json);

                            notify('Insole data loaded','success');
                        }

                    } catch(e) {
                        notify('Error parsing shoe template: ' + e.message, 'error')
                    }
                }
                reader.readAsArrayBuffer(file);

            }
        }

        // reset file loader
        $('#loadProject').val('');
    });
}


// GUI event handler
function reactToChanges(newVal) {
    console.log('reactToChanges');

    if (this.lastVal && newVal == this.lastVal) return;

    regen();
    //updateDXFGroup();
    //updateFootGroup();

    if (insock.thicknessChanged) {
        insock.thicknessChanged = false;
        //extrudeModifiers();
        //updateModifierInfo();
    }

    if (this.property) {
        this.lastVal = newVal;
    }
}


// Init and UI

$(document).ready(function(){

    // init 3D environment
    init();

    // build UI
    gui = new dat.GUI();

/*
    guiFPatient = gui.addFolder('Patient');
    guiFPatient.add(patient, 'bodyWeight').step(0.1).name('Body Weight (kg)').onChange(updateFootGroup);
    guiFPatient.add(patient, 'activityLevel', [ 'walking','running' ]).name('Activity Level');
    */


    guif3 = gui.addFolder('Foot Scan');

    guif4 = gui.addFolder('Advanced');
    guif4.add(insock, 'modifierZOffset').step(0.01).name('Modifier Z Offset').onChange(function() {
        insock.thicknessChanged = true;
        reactToChanges();
    });
    guif4.add(insock, 'showUpperSurface').name('Show Upper Surface?');
    guif4.add(insock, 'triangleSize',[0.5,1,2,3,4,5,10]).name('Triangle Size');

/*
    guif3.add(footScan, 'x').step(0.1).name('X Offset').onChange(updateFootGroup);
    guif3.add(footScan, 'y').step(0.1).name('Y Offset').onChange(updateFootGroup);
    guif3.add(footScan, 'z').step(0.1).name('Z Offset').onChange(updateFootGroup);
    guif3.add(footScan, 'xr').step(0.1).name('X Rotation').onChange(updateFootGroup);
    guif3.add(footScan, 'yr').step(0.1).name('Y Rotation').onChange(updateFootGroup);
    guif3.add(footScan, 'zr').step(0.1).name('Z Rotation').onChange(updateFootGroup);
    */
    guif3.add(footScan, 'numPlanes',1,10).step(1).name('# Planes').onChange(updateFootGroup);
    guif3.add(footScan, 'planeStart',0,100).step(0.1).name('Start At').onChange(updateFootGroup);
    guif3.add(footScan, 'planeOffset',0.1,10).step(0.1).name('Plane Spacing').onChange(updateFootGroup);

    // things that shouldn't have an onFinishChange event!
    guif4.add(insock, 'relaxIterations', [0,1,3,5,10,15,20]).name('Relax Iterations').onChange(reactToChanges);


    // fade in gui
    $('.dg.ac').fadeIn('slow');


    $('#soleMorphBut').change(function() {
        insock.calcContour = $(this).prop('checked');
        regen(genStages.updateSurfaceContour);
    });



    // toolbar
    $('#translateToolbarBut').click(function() {
        transformControl.setMode('translate');
        needsRender=true;
    });

    $('#rotateToolbarBut').click(function() {
        transformControl.setMode('rotate');
        needsRender=true;
    });

    $('#showFootBut').click(function() {
        footScan.hideFoot = $('#showFootBut input').is(':checked');
        needsRender=true;
    });

    $('#showModifiersBut').click(function() {
        insock.hideModifiers = $('#showModifiersBut input').is(':checked');
        needsRender=true;
    });

    // Material options
    $('#matGlassBut').change(function() {
        insock.renderMode = 'glass';
        if (insockMesh) insockMesh.material = getInsockMaterial();
        needsRender=true;
    });

    $('#matSolidBut').change(function() {
        insock.renderMode = 'solid';
        if (insockMesh) insockMesh.material = getInsockMaterial();
        needsRender=true;
    });

    $('#matWireBut').change(function() {
        insock.renderMode = 'wireframe';
        if (insockMesh) insockMesh.material = getInsockMaterial();
        needsRender=true;
    });

    $('#archSupportBut').change(function() {
        insock.archSupport = $(this).prop('checked');
        regen();
    });

    // Camera options
    $('#camPerBut').change(function() {
        cameraMode = true;
        amfCamera.matrixWorldInverse.copy(amfCameraOrt.matrixWorldInverse);
        amfCamera.position.copy(amfCameraOrt.position);
        activeCamera = amfCamera;
        amfControls.object = activeCamera;
        transformControl.camera = activeCamera;
        transformControl.update();
        needsRender=true;
    });
    $('#camOrtBut').change(function() {
        cameraMode = false;
        amfCameraOrt.matrixWorldInverse.copy(amfCamera.matrixWorldInverse);
        amfCameraOrt.position.copy(amfCamera.position);
        activeCamera = amfCameraOrt;
        amfControls.object = activeCamera;
        transformControl.camera = activeCamera;
        transformControl.update();
        needsRender=true;
    });

    $('#camTurntableBut').change(function() {
        turntableEnabled = $('#camTurntableBut input').is(':checked');
        // start orbit timer
        if (turntableEnabled)
            autoRotateTimer = setTimeout(function() {
                amfControls.autoRotate=true;
                amfControls.autoRotateSpeed = 0;
            },1000);
    });

    // tooltips
    $('[data-toggle="tooltip"]').tooltip({
        delay:200,
        placement:'bottom'
    });


    /*
        Shoe Library
    */
    initShoeLibrary();


    /*
       Patient libary
    */
    initPatientLibrary();

    // Patient loader
    initPatientLoader();


    // uiFSM initialisation will cause transition into "patient" state and initial render

    // stats
    stats = new Stats();
    stats.setMode( 1 );
    document.body.appendChild( stats.domElement );


    /*
        DXF file loader
    */
    var fileInput = document.getElementById('loadDxf');
    fileInput.addEventListener('change', function (event) {

        modifierMode = 'dxf';

        resetFootScan();

        var fileUploader = this;
        var files = event.target.files;
        if (files.length > 0) {
            for (var i=0; i<files.length; i++) {
                var file = files[i];
                if (file.name.endsWith('dxf')) {

                    fileReaderQueue.push(file);
                }
            };

            readFiles();
        }

        // reset file loader
        $('#loadDxf').val('');

    });


    $('#rootwizard').bootstrapWizard({
        'tabClass': 'nav nav-pills',
         onTabShow: function(tab, navigation, index) {
             // update ui state machine
             if (index == 0 && !uiFSM.is('patient')) uiFSM.toPatient()
             else if (index == 1 && !uiFSM.is('profile')) uiFSM.toProfile()
             else if (index == 2 && !uiFSM.is('soleMorph')) uiFSM.toSoleMorph()
             else if (index == 3 && !uiFSM.is('modifiers')) uiFSM.toModifiers();
	     }
    });
    $('#rootwizard').fadeIn('slow');



    $('#leftBut').click(function() {
        uiFSM.left();
    });

    $('#rightBut').click(function() {
        uiFSM.right();
    });

    $('#nextBut1').click(function() {
        uiFSM.toSoleMorph();
    });

    $('#nextBut2').click(function() {
        uiFSM.toModifiers();
    });


    $('#sliceBut').click(function() {
        sliceAMF();
    });

    $('#contourBut').click(function() {
        console.log('contouring...');
        updateSurfaceContourOfModifiers();
        needsRender = true;
    });

    $('#downloadZipBut').click(function() {
        downloadZip();
    });

    /*
        Scan (STL) file loader
    */
    var stlFileInput = document.getElementById('loadScan');
    stlFileInput.addEventListener('change', function (event) {

        modifierMode = 'stl';

        var fileUploader = this;
        var files = event.target.files;
        if (files.length > 0) {
            var file = files[0];
            if (file.name.endsWith('stl')) {
                var fr2 = new FileReader();

                fr2.onload = function(e) {
                     loadScanSTL(fr2.result);
                };

                fr2.readAsText(file);
            }
        }

        // reset file loader
        $('#loadScan').val('');
    });


    // trigger render loop
    render();
});

function updatePatientInfo() {
    modifierMode = 'none';

    var hideFootStatus = footScan.hideFoot,
        hideModifiersStatus = insock.hideModifiers,
        renderModeStatus = insock.renderMode;

    // reset everything!
    resetFootScan();

    patient.name = $('#patientName').val();
    patient.bodyWeight = parseFloat($('#bodyWeight').val());
    if (isNaN(patient.bodyWeight) || patient.bodyWeight < 0 || patient.bodyWeight > 500 ) {
        patient.bodyWeight = 1;
        $('#bodyWeight').val(1);
    }

    if (selectedPatient) {
        // don't need to reset these, already set during load project
        //patient.name = selectedPatient.name;
        //patient.bodyWeight = selectedPatient.bodyWeight;

        if (insock.whichFoot == 'Left') {
            if (selectedPatient.left) {
                insock = $.extend(insock, selectedPatient.left.profile);
                footScan = $.extend(footScan, selectedPatient.left.footScan);
                selectedPatient.data = selectedPatient.left;
            }
        } else {
            if (selectedPatient.right) {
                insock = $.extend(insock, selectedPatient.right.profile);
                footScan = $.extend(footScan, selectedPatient.right.footScan);
                selectedPatient.data = selectedPatient.right;
            }
        }

        regen(0, genStages.rebuildProfileMesh);

        // assume we've loaded something... so reset Foot Scan properties

        insock.hideModifiers = hideModifiersStatus;
        footScan.hideFoot = hideFootStatus;
        insock.renderMode = renderModeStatus;
        footScan.x = 0;
        footScan.y = 0;
        footScan.z = 0;
        footScan.xr = 0;
        footScan.yr = 0;
        footScan.zr = 0;

        // reading from zip?  or server?
        if (selectedPatient.zip) {
            if (insock.modifierMode) {

                // load the new stuff
                if (insock.modifierMode == 'stl') {
                    // load foot
                    modifierMode = insock.modifierMode;
                    var fn = selectedPatient.zipDir + insock.whichFoot + '-Foot.stl';
                    loadScanSTL(selectedPatient.zip.file(fn).asText());

                    // TODO: how to reinstate manual modifier densities??

                } else if (insock.modifierMode == 'dxf' && selectedPatient.data.modifiers) {
                    // load DXF modifiers
                    var loadCount = selectedPatient.data.modifiers.length;
                    var loadTotal = loadCount;

                    selectedPatient.data.modifiers.map(function(m) {
                        //url:"/library/" + m.filenameDXF,
                        console.log('Loading: '+m.filenameDXF);
                        var fn = m.filenameDXF;
                        parseDXF(m.group, selectedPatient.zip.file(fn).asText(), m.density);

                        loadCount--;

                        if (loadCount == 0) {
                            updateDXFGroup();
                            extrudeModifiers();
                            //updateModifierInfo();
                            needsRender = true;
                        }
                    });


                    modifierMode = insock.modifierMode;
                }
            }
        } else {
            // do we need to load modifers?  or stl?
            if (insock.modifierMode) {

                // load the new stuff
                if (insock.modifierMode == 'stl') {
                    // load foot
                    $('#circle').circleProgress({
                        value: 0,
                        size: 80,
                        fill: {
                            gradient: ["red", "orange"]
                        }
                    });
                    $('#circle').fadeIn('fast');

                    $.ajax({
                      xhr: function()
                      {
                        var xhr = new window.XMLHttpRequest();
                        //Download progress
                        xhr.addEventListener("progress", function(evt){
                          if (evt.lengthComputable) {
                            var percentComplete = evt.loaded / evt.total;
                            //Do something with download progress
                            $('#circle').circleProgress({
                                value: percentComplete,
                                size: 80,
                                animation:false,
                                fill: {
                                    gradient: ["red", "orange"]
                                }
                            });
                          }
                        }, false);
                        return xhr;
                      },
                      type: 'GET',
                      url: "/library/" + patient.name + '/' + insock.whichFoot + '-Foot.stl',
                      data: {},
                      success: function(data){
                          modifierMode = insock.modifierMode;
                          loadScanSTL(data);
                          $('#circle').fadeOut('fast');
                      },
                      error :function(data) {
                          $('#circle').fadeOut('fast');
                      }
                    });


                } else if (insock.modifierMode == 'dxf' && selectedPatient.data.modifiers) {
                    // load DXF modifiers

                    $('#circle').circleProgress({
                        value: 0,
                        size: 80,
                        fill: {
                            gradient: ["red", "orange"]
                        }
                    });
                    $('#circle').fadeIn('fast');

                    var loadCount = selectedPatient.data.modifiers.length;
                    var loadTotal = loadCount;

                    selectedPatient.data.modifiers.map(function(m) {
                        $.ajax({
                            url:"/library/" + m.filenameDXF,
                            method:'GET',
                            cache: false,
                            success:function( data ) {
                                console.log('Loading: '+m.filenameDXF);
                                parseDXF(m.group, data, m.density);

                                loadCount--;

                                $('#circle').circleProgress({
                                    value: (loadTotal - loadCount) / loadTotal,
                                    size: 80,
                                    animation:false,
                                    fill: {
                                        gradient: ["red", "orange"]
                                    }
                                });

                                if (loadCount == 0) {
                                    updateDXFGroup();
                                    extrudeModifiers();
                                    //updateModifierInfo();
                                    needsRender = true;
                                    $('#circle').fadeOut('fast');
                                }

                            }
                        });
                    });

                    modifierMode = insock.modifierMode;
                }
            }

        }

    } else {

        regen();
    }

    // update GUI with whatever we've loaded
    setTimeout(updateGUI, 100);
}



function updateFootGroup(newVal) {
    //if (this.lastVal && newVal == this.lastVal) return;

    if (footObj && modifierMode == 'stl') {
        amfFoot.position.set(footScan.x, footScan.y, footScan.z);
        amfFoot.rotation.set(degToRad(footScan.xr), degToRad(footScan.yr), degToRad(footScan.zr));
        footObj.updateMatrixWorld();

        transformControl.attach(amfFoot);

        // recalc contour
        regen(genStages.updateSurfaceContour);

    } else if (modifierMode == 'dxf') {
        transformControl.attach(amfDXF);
    }

    if (this.property) {
        this.lastVal = newVal;
    }
}



function DistFromPlane(p, plane) {
    return plane.normal.dot(p) + plane.d;
}

function LinePlaneIntersection(p1,p2,plane) {
    var i = {
        intersects:false,
        atP1:false,
        atP2:false,
        points:[]
    };
    var eps = 0.0001;

    var d1 = DistFromPlane(p1, plane),
        d2 = DistFromPlane(p2, plane);

    i.atP1 = (Math.abs(d1) <= eps),
    i.atP2= (Math.abs(d2) <= eps);

    if (i.atP1)
        i.points.push(p1.clone());

    if (i.atP2)
        i.points.push(p2.clone());

    i.liesOnPlane = i.atP1 && i.atP2;

    i.intersects = i.points.length > 0;

    if (i.atP1 && i.atP2)  // both points lie in plane
        return i;

    if (d1*d2 > eps) // points on same side of plane
        return i;

    var t = d1 / (d1 - d2);
    if (t >=0 && t <= 1) {
        var p3 = p2.clone();
        p3.sub(p1).multiplyScalar(t).add(p1);
        i.points.push(p3);

        i.intersects = true;
    }


    return i;
}

// returns a collection of intersection segments
function FacePlaneIntersection(p1,p2,p3,normal, plane)
{
    // test edges
    var e1 = LinePlaneIntersection(p1,p2,plane);
    var e2 = LinePlaneIntersection(p2,p3,plane);
    var e3 = LinePlaneIntersection(p3,p1,plane);

    var ni = 0;
    if (e1.intersects) ni++;
    if (e2.intersects) ni++;
    if (e3.intersects) ni++;

    var i = {
        numIntersections: ni,
        intersects:ni > 0,
        liesOnPlane: e1.liesOnPlane && e2.liesOnPlane && e3.liesOnPlane,
        points: [],
        normal:normal
    };

    if (ni > 2 && !i.liesOnPlane) {
        // pick two points that are furthest away from each other
        var d12 = e1.points[0].distanceToSquared(e2.points[0]);
        var d13 = e1.points[0].distanceToSquared(e3.points[0]);
        var d23 = e2.points[0].distanceToSquared(e3.points[0]);

        i.points = [];

        if (d12 > d13) {
            if (d12 > d23) {
                i.points = [e1.points[0], e2.points[0]];
            } else {
                i.points = [e2.points[0], e3.points[0]];
            }
        } else {
            if (d13 > d23) {
                i.points = [e1.points[0], e3.points[0]];
            } else {
                i.points = [e2.points[0], e3.points[0]];
            }
        }
        i.numIntersections = 2;
    } else if (ni > 0) {
        i.points = e1.points;
        i.points = i.points.concat(e2.points);
        i.points = i.points.concat(e3.points);
    }

    return i;
}



function updateSurfaceContour() {
    if (footObj === undefined || modifierMode != 'stl' || insockMesh === undefined) return true;

    if (insock.status != 'valid') return false;

    console.time('updateSurfaceContour');

    // clone and bake footObj
    footObj.updateMatrixWorld();

    if (bakedFootGeo)
        bakedFootGeo.dispose();

    bakedFootGeo = footObj.geometry.clone();
    bakedFootGeo.applyMatrix(footObj.matrixWorld);


    // either reset or contour surface
    if (!insock.calcContour) {

        // reset vertices
        for (var i=insock.extraIndex; i < insockMesh.geometry.vertices.length; i++) {
            var v = insockMesh.geometry.vertices[i];
            if (v.orig) v.set(v.orig[0], v.orig[1], v.orig[2]);
        }


    } else {
        // place faces of interest within a basic spacial division grid
        var testRegions = [];

        // prep regions
        var cellsX = 4, cellsY = 8;
        var b = new THREE.Box2(
            new THREE.Vector2((insock.whichFoot == 'Left' ? -insock.ow : -insock.iw), -20),
            new THREE.Vector2((insock.whichFoot == 'Left' ? insock.iw : insock.ow), insock.l + 20)
        );
        b.width = b.max.x - b.min.x;
        b.height = b.max.y - b.min.y;

        for (var x=0; x<cellsX; x++) {
            for (var y=0; y<cellsY; y++) {
                var xu = x / (cellsX),
                    yu = y / (cellsY);

                testRegions.push({
                    bounds: new THREE.Box2(
                        new THREE.Vector2(b.min.x + xu * (b.width), b.min.y + yu * (b.height) ),
                        new THREE.Vector2(b.min.x + (xu) * b.width + b.width/cellsX, b.min.y + (yu) * (b.height) + b.height/cellsY)
                    ),
                    faces: [],
                    faces2: []
                });
            }
        }

        // obtain "faces of interest" from foot scan
        var geo = bakedFootGeo;
        var _z = Math.max(insock.t, insock.tt, insock.archHeight);
        geo.faces.map(function(f, index) {
            var a = geo.vertices[f.a];
            var b = geo.vertices[f.b];
            var c = geo.vertices[f.c];

            if ((a.z < _z || b.z < _z || c.z < _z) && (f.normal.z < 0)) {
                var bounds = new THREE.Box2(
                    new THREE.Vector2(Math.min(a.x,b.x,c.x), Math.min(a.y,b.y,c.y)),
                    new THREE.Vector2(Math.max(a.x,b.x,c.x), Math.max(a.y,b.y,c.y))
                );
                for (var i=0; i<testRegions.length; i++) {
                    if (testRegions[i].bounds.isIntersectionBox(bounds)) {
                        testRegions[i].faces.push({
                            vertices: [a,b,c],
                            bounds: bounds
                        });
                    }
                }

            }
        });


        // modify the z value of our "extra" vertices
        var testDist = sqr(15);
        var ray = new THREE.Ray(new THREE.Vector3(0, 0, -50), new THREE.Vector3(0,0,1));
        var v2d = new THREE.Vector2(0,0);
        for (var i=insock.extraIndex; i < insockMesh.geometry.vertices.length; i++) {
            var v = insockMesh.geometry.vertices[i];
            v.contact = false;

            // reset z value?
            if (v.orig) v.z = v.orig[2];

            ray.origin.set(v.x, v.y, -50);

            // find lowest intersection with foot scan
            v2d.set(v.x, v.y);

            for (var j=0; j<testRegions.length; j++) {
                if (testRegions[j].bounds.containsPoint(v2d)) {
                    testRegions[j].faces.map(function(f) {
                        var a = f.vertices[0], b=f.vertices[1], c=f.vertices[2];

                        if ((a.z < v.z || b.z < v.z || c.z < v.z) && (f.bounds.containsPoint(v2d))) {
                            // of interest
                            var intersect = ray.intersectTriangle(a,b,c, true);
                            if (intersect) {
                                if (intersect.z < v.z) {
                                    v.z = intersect.z;
                                    if (v.z < 3*insock.modifierZOffset)
                                        v.z = 3*insock.modifierZOffset;
                                    v.contact = true;
                                }
                            }
                        }

                    });
                }
            }

        }

    }


    insockMesh.geometry.verticesNeedUpdate = true;
    insockMesh.geometry.normalsNeedUpdate = true;
    insockMesh.geometry.computeFaceNormals();

    console.timeEnd('updateSurfaceContour');

    return true;
}

function relaxSurfaceContour() {

    if (!insock.calcContour || modifierMode != 'stl' || footObj === undefined || insockMesh === undefined) return true;

    if (genFlags.relaxInterationsDone === undefined) genFlags.relaxInterationsDone = 0;

    genFlags.relaxInterationsDone++;

    // reset dims
    while (amfDims2.children.length > 0) {
        var tmp = amfDims2.children[0];
        amfDims2.remove(tmp);
        disposeObject(tmp);
    }


    insock.minThicknessPlantar = new THREE.Vector3(0, insock.l, insock.tt);
    insock.minThicknessHeel = new THREE.Vector3(0, 0, insock.t);

    //console.time('relax');

    //console.log('relax', insock.extraIndex);

    function addNeighbours(v1,v2) {
        if (!v1.neighbours) v1.neighbours = [];
        if (!v2.neighbours) v2.neighbours = [];

        // add v2 to v1
        var found = false;
        v1.neighbours.map(function(v3) {
            if (v3 == v2) found=true;
        });
        if (!found) v1.neighbours.push(v2);

        // add v1 to v2
        found = false;
        v2.neighbours.map(function(v3) {
            if (v3 == v1) found=true;
        });
        if (!found) v2.neighbours.push(v1);
    }

    // build vertex neighbour lists, cache for later
    if (!insockMesh.geometry.neighbourCache) {
        insockMesh.geometry.faces.map(function(f) {
            if (f.a >= insock.extraIndex || f.b >= insock.extraIndex || f.c >= insock.extraIndex) {
                var va = insockMesh.geometry.vertices[f.a],
                    vb = insockMesh.geometry.vertices[f.b],
                    vc = insockMesh.geometry.vertices[f.c];

                addNeighbours(va,vb);
                addNeighbours(va,vc);
                addNeighbours(va,vb);
            }
        });
    }

    insockMesh.geometry.neighbourCache = true;

    // relax surface?


    var numIterations = 1;
    for (var j=0; j < numIterations; j++) {
        for (var i=insock.extraIndex; i < insockMesh.geometry.vertices.length; i++) {
            var v = insockMesh.geometry.vertices[i];


            // relax this vertex


            // sum forces from neighbours
            if (v.neighbours && v.neighbours.length > 0) {
                v.f = new THREE.Vector3(0,0,0);

                v.neighbours.map(function(vn) {
                    v.f.add(vn);
                });

                v.f.multiplyScalar(1 / v.neighbours.length);
                v.f.sub(v);

                // attenuate
                v.f.multiplyScalar(v.contact ? 0.2 : 1);
            }
        }

        // apply the new z values
        for (var i=insock.extraIndex; i < insockMesh.geometry.vertices.length; i++) {
            var v = insockMesh.geometry.vertices[i];
            if (v.f) v.add(v.f);

            // update min thickness values
            if (v.y < insock.l / 3) {
                if (v.z < insock.minThicknessHeel.z)
                    insock.minThicknessHeel.copy(v);
            } else if (v.y > insock.l / 2) {
                if (v.z < insock.minThicknessPlantar.z)
                    insock.minThicknessPlantar.copy(v);
            }
        }
    }

    // make sure the upper surface doesn't penetrate the sides
    if (genFlags.relaxInterationsDone >= insock.relaxIterations) {
        var ray = new THREE.Ray(new THREE.Vector3(0, 0, insock.t), new THREE.Vector3(0,0,-1));
        var v2d = new THREE.Vector2(0,0);

        var minFaceIndex = 2*insock.inPoints.length;
        var maxFaceIndex = 10*insock.inPoints.length;

        for (var i=insock.extraIndex; i < insockMesh.geometry.vertices.length; i++) {
            var v = insockMesh.geometry.vertices[i];
            ray.origin.set(v.x, v.y, -50);

            v2d.set(v.x, v.y);

            // test against all normal faces
            insockMesh.geometry.faces.map(function(f) {
                if (f.a <= maxFaceIndex && f.b <= maxFaceIndex && f.c <= maxFaceIndex) {
                    var a = insockMesh.geometry.vertices[f.a],
                        b = insockMesh.geometry.vertices[f.b],
                        c = insockMesh.geometry.vertices[f.c];

                    // TODO: add distance test?
                    if ((a.z > v.z || b.z > v.z || c.z > v.z)) {
                        // of interest
                        var intersect = ray.intersectTriangle(a,b,c, true);
                        if (intersect) {
                            if (intersect.z + 1 > v.z) {
                                v.z = intersect.z + 1;
                                v.contact = true;
                            }
                        }
                    }
                }

            });
        }
    }

    //console.timeEnd('relax');

    insockMesh.geometry.verticesNeedUpdate = true;
    insockMesh.geometry.normalsNeedUpdate = true;
    insockMesh.geometry.computeFaceNormals();
    //insockMesh.geometry.computeVertexNormals();


    // update min thickness dimensions
    var dl = MakeDimLine(
            0,
            insock.t + 25,
            0,
            insock.t + 25,
            "Min Thickness: "+insock.minThicknessHeel.z.toFixed(1),
            0,
            0,
            0,
            0
    );
    dl.g.rotation.x = Math.PI/2;
    dl.g.rotation.y = Math.PI;
    dl.g.position.x = insock.minThicknessHeel.x;
    dl.g.position.y = insock.minThicknessHeel.y;
    amfDims2.add(dl.g);

    dl = MakeDimLine(
            0,
            insock.t + 25,
            0,
            insock.t + 25,
            "Min Thickness: "+insock.minThicknessPlantar.z.toFixed(1),
            0,
            0,
            0,
            0
    );
    dl.g.rotation.x = Math.PI/2;
    dl.g.rotation.y = Math.PI;
    dl.g.position.x = insock.minThicknessPlantar.x;
    dl.g.position.y = insock.minThicknessPlantar.y;
    amfDims2.add(dl.g);

    needsRender = true;  // so we can see progressive refinement :)
    // returns true once complete

    return (genFlags.relaxInterationsDone >= insock.relaxIterations);
}


function updateSurfaceContourOfModifiers() {
    console.time('updateSurfaceContourOfModifiers');

    remeshModifiers();

    var testRegions = [];

    // prep regions
    var cellsX = 4, cellsY = 8;
    var mx = Math.max(insock.ow, insock.iw, insock.hr) + 10;
    var b = new THREE.Box2(
        new THREE.Vector2(-mx, -20),
        new THREE.Vector2(mx, insock.l + 20)
    );
    b.width = b.max.x - b.min.x;
    b.height = b.max.y - b.min.y;

    for (var x=0; x<cellsX; x++) {
        for (var y=0; y<cellsY; y++) {
            var xu = x / (cellsX),
                yu = y / (cellsY);

            testRegions.push({
                bounds: new THREE.Box2(
                    new THREE.Vector2(b.min.x + xu * (b.width), b.min.y + yu * (b.height) ),
                    new THREE.Vector2(b.min.x + (xu) * b.width + b.width/cellsX, b.min.y + (yu) * (b.height) + b.height/cellsY)
                ),
                faces: []
            });
        }
    }

    // update spatial grid
    var ray = new THREE.Ray(new THREE.Vector3(0, 0, 0), new THREE.Vector3(0,0,1));

    insockMesh.geometry.faces.map(function(f) {
        if (f.a >= insock.extraIndex || f.b >= insock.extraIndex || f.c >= insock.extraIndex) {
            var va = insockMesh.geometry.vertices[f.a],
                vb = insockMesh.geometry.vertices[f.b],
                vc = insockMesh.geometry.vertices[f.c];

            var bounds = new THREE.Box2(
                new THREE.Vector2(Math.min(va.x,vb.x,vc.x), Math.min(va.y,vb.y,vc.y)),
                new THREE.Vector2(Math.max(va.x,vb.x,vc.x), Math.max(va.y,vb.y,vc.y))
            );
            for (var i=0; i<testRegions.length; i++) {
                if (testRegions[i].bounds.isIntersectionBox(bounds)) {
                    testRegions[i].faces.push({
                        vertices: [va,vb,vc],
                        bounds: bounds
                    });
                }
            }
        }
    });

    // intersect each mesh with the insock upper surface
    var zMax = Math.min(insock.modifierZMax, (Math.max(insock.t, insock.tt, insock.archHeight) - insock.modifierZOffset)) - insock.modifierZOffset;
    modifiers.map(function(m, mindex) {
        if (!m.mesh) return;

        var vertexCount = 0;

        for (var i=0; i < m.mesh.geometry.vertices.length; i++) {
            var v = m.mesh.geometry.vertices[i];

            // if these are DXF modifiers, then need to take account of transforms!
            if (modifierMode == 'dxf')
                v = v.clone().applyMatrix4(amfDXF.matrixWorld);

            if (v.z > 0.1) {

                // reset z
                v.z = zMax;

                ray.origin.set(v.x, v.y, 0);

                // find lowest intersection with foot scan
                var v2d = new THREE.Vector2(v.x, v.y);

                for (var j=0; j<testRegions.length; j++) {
                    if (testRegions[j].bounds.containsPoint(v2d)) {

                        testRegions[j].faces.map(function(f) {

                            var a = f.vertices[0], b=f.vertices[1], c=f.vertices[2];

                            if ( f.bounds.containsPoint(v2d) ) {
                                // of interest
                                var intersect = ray.intersectTriangle(a,b,c, false);
                                if (intersect) {
                                    if (intersect.z - 2*insock.modifierZOffset < v.z) {
                                        vertexCount++;
                                        v.z = intersect.z - 2*insock.modifierZOffset;
                                    }
                                }
                            }

                        });
                    }
                }

                m.mesh.geometry.vertices[i].z = v.z;
            }

        }

        m.mesh.geometry.verticesNeedUpdate = true;
    });

    needsRender=true;

    console.timeEnd('updateSurfaceContourOfModifiers');
}


function calcFootIntersections() {

    if (modifierMode != 'stl' || footObj === undefined) return true;

    console.time('calcFootIntersections');

    // for each slicing plane
    var numPlanes = footScan.numPlanes;
    var planeOffset = footScan.planeOffset;


    // reset modifiers
    resetModifiers();

    for (var i=0; i<numPlanes; i++) {
        var plane = {
            z:i*planeOffset,
            d:-footScan.planeStart - i*planeOffset,
            normal: new THREE.Vector3(0,0,1),
            index:i
        };

        calcFootIntersectionsForPlane(plane, bakedFootGeo);
    }

    console.timeEnd('calcFootIntersections');

    extrudeModifiers();

    updateModifierInfo();
    needsRender = true;

    return true;
}

function calcFootIntersectionsForPlane(plane, geo) {

    try {
        // calc plane intersections

        eps = 0.1;  // tolerance

        // intersection segments
        var seg = [];

        // for each face in foot
        geo.faces.map(function(f) {
            // test for intersection with plane
            // get vertices in world coordinates
            var a = geo.vertices[f.a];
            var b = geo.vertices[f.b];
            var c = geo.vertices[f.c];

            var newSeg = FacePlaneIntersection(a, b, c, f.normal, plane);

            if (newSeg.numIntersections == 2) {
                seg.push(newSeg);
            }

        });


        // collection of paths, each contains an array of vertices
        var paths = [];

        if (seg.length > 0) {
            // pop a segment and use it to start a closed path
            var curPath = {segments:[seg.pop()]};
            paths.push(curPath);

            while (seg.length > 0) {
                // current segment is last in curPath
                var s1 = curPath.segments[curPath.segments.length-1];

                // now find the segment that joins to the end of the last segment
                var match = -1;
                var ds = 1000;
                var flip = false;
                for (var i=0; i<seg.length; i++) {
                    var s2 = seg[i];

                    // check both ends of s2
                    var es = s1.points[1].distanceToSquared(s2.points[0]);
                    var ee = s1.points[1].distanceToSquared(s2.points[1]);

                    if (es < ds) {
                        match = i;
                        ds = es;
                        flip = false;
                    }
                    if (ee < ds) {
                        match = i;
                        ds = ee;
                        flip = true;
                    }
                }

                if (match > -1 && ds < eps) {
                    var s2 = seg.splice(match,1)[0];
                    if (flip) {
                        // swap segment Direction
                        var v = s2.points[0];
                        s2.points[0] = s2.points[1];
                        s2.points[1] = v;
                    }
                    curPath.segments.push(s2);
                } else {
                    // start a new path
                    curPath = {segments:[seg.pop()]};
                    paths.push(curPath);
                }
            }

            // render each path
            var cv1 = new THREE.Vector3();
            var cv2 = new THREE.Vector3();
            var sv = new THREE.Vector3();
            var lsv = new THREE.Vector3();
            paths.map(function(p, index) {
                var shape = new THREE.Shape();
                shape.moveTo(p.segments[0].points[0].x, p.segments[0].points[0].y);
                shape.lineTo(p.segments[0].points[1].x, p.segments[0].points[1].y);
                lsv.copy(p.segments[0].points[1]).sub(p.segments[0].points[0]);
                var vecSigns = 0;
                for (var i=1; i<p.segments.length; i++) {
                    // check distance from last point
                    var d = p.segments[i].points[1].distanceToSquared(p.segments[i-1].points[1]);
                    if (d > 0.1)
                        shape.lineTo(p.segments[i].points[1].x, p.segments[i].points[1].y);

                    // cross segment vector with face normal
                    sv.copy(p.segments[i].points[1]).sub(p.segments[i].points[0]);
                    cv1.crossVectors(p.segments[i].normal, sv);

                    // also cross segment vector with last segment vector
                    cv2.crossVectors(sv, lsv);

                    // vecSigns will be positive for interior regions, negative for exterior regions
                    vecSigns += (cv1.z > 0 ? 1 : -1) * (cv2.z > 0 ? 1 : -1);
                    lsv.copy(sv);
                }

                var flatGeo = new THREE.ShapeGeometry(shape);
                flatGeo.mergeVertices();

                var areacm2 = 0.01 * SurfaceAreaOfGeometry(flatGeo);

                // filter out small regions or interior regions
                if (areacm2 > 2 && vecSigns < 0) {
                    var points = shape.createPointsGeometry();
                    var obj = new THREE.Line( points, new THREE.LineBasicMaterial( { color: vecSigns > 0 ? 0xFF0000 : 0x00FF00, linewidth: 1 } ) );
                    obj.position.z = -plane.d;
                    amfFootIntersections.add(obj);

                    addModifier("Plane at z="+plane.z.toFixed(2), index, -1, shape, flatGeo, amfFootIntersections, plane.index);
                }

            });

        }
    } catch(e) {
        console.log('Error calculating intersections! '+e.message);
    }
}


function extrudeModifiers() {
    // update modifier extrusions, e.g. following a rescale of the insock Thickness

    console.time('extrudeModifiers');

    resetDXFGroup();

    if (modifiers.length > 0) {
        modifiers.map(function(m,index) {

            // remove old mesh
            if (m.mesh) {
                m.g.remove(m.mesh);
                m.mesh.geometry.dispose();
                m.mesh.material.dispose();
                m.mesh = null;
            }

            // calc areas, pressure, density
            m.areamm2 =SurfaceAreaOfGeometry(m.flatGeo);
            m.areacm2 = m.areamm2 * 0.01;
            m.aream2 = m.areacm2 * 0.0001;
            var newtons = 9.80665 * patient.bodyWeight * 1.2;
            m.pressure =  newtons / m.aream2;

            // calc clamped pressure for density formula, capped to 200kPa
            var p2 = clamp(m.pressure/1000,1,200);
            // use layer height instead
            var density = 20 - m.planeIndex * 5;

            m.calculatedDensity = clamp(density,1,100);
            if (m.density <0) m.density = m.calculatedDensity;


            // extrude
            var extrudeSettings = { amount: 0.2 + (0.1-m.aream2), bevelEnabled: false };
            var geometry = new THREE.ExtrudeGeometry( m.shape, extrudeSettings );
            geometry.mergeVertices();
            geometry.dynamic = true;
            geometry.remeshed = false;


            m.mesh = new THREE.Mesh( geometry, new THREE.MeshLambertMaterial({
                overdraw:true,
                color: colorByDensity(m.density/100),
                transparent:true,
                opacity: 0.5,
                shading: THREE.FlatShading,
                blending: THREE.MultiplyBlending,
                depthTest:false,
                depthWrite:false
            }) );


            m.mesh.renderOrder = 101;
            m.mesh.position.z = insock.modifierZOffset;

            m.remeshed = false;


            m.g.add( m.mesh );
        });
    }

    console.timeEnd('extrudeModifiers');

    updateDXFGroup();
}


function remeshModifiers() {

    var tesselator = new THREE.TessellateModifier(insock.triangleSize * 2, 0.5);
    var iterations = 25;

    if (modifiers.length > 0) {
        modifiers.map(function(m,index) {

            if (m.remeshed) return;

            m.remeshed = true;

            var extrudeSettings = { amount: 1, bevelEnabled: false };
            var geometry = new THREE.ExtrudeGeometry( m.shape, extrudeSettings );
            geometry.mergeVertices();
            geometry.dynamic = true;

            // tesselate upper surface
            for (var i=0; i < iterations; i++) {
                if (!tesselator.modify(geometry)) break;
            }

            geometry.mergeVertices();

            // remove old mesh
            if (m.mesh) {
                m.g.remove(m.mesh);
                m.mesh.geometry.dispose();
                m.mesh.material.dispose();
                m.mesh = null;
            }

            // create new mesh
            /*
            m.mesh = new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({
                color: colorByDensity(m.density/100),
                shading: THREE.FlatShading,
                side:THREE.DoubleSide,
                blending: THREE.MultiplyBlending,
                wireframe:true
            }));
            */
            m.mesh = new THREE.Mesh( geometry, new THREE.MeshLambertMaterial({
                overdraw:true,
                color: colorByDensity(m.density/100),
                transparent:true,
                opacity: 0.5,
                shading: THREE.FlatShading,
                blending: THREE.MultiplyBlending,
                depthTest:false,
                depthWrite:false
            }) );

            m.mesh.renderOrder = 101;
            m.mesh.position.z = insock.modifierZOffset;

            m.g.add( m.mesh );
        });
    }
}


function updateModifierInfo() {
    var src = '';

    modifiers.sort(function(a,b) {
        return a.group > b.group;
    });

    if (modifiers.length > 0) {
        var g = '';
        src = '<div class="panel-heading">Density Zones</div>';

        modifiers.map(function(i,index) {
            if (i.group != g) {
                if (index > 0) {
                    src += '</table>';
                }
                src += '<div class="panel-body"><b>'+i.group+'</b></div>';
                src += '<table class="table">';
                src += '<tr><th>ID</th> <th>Area</th> <th>Pressure</th> <th>Density</th> </tr>'
                g = i.group;
            }
            src += '<tr>'
            src += '<td>'+i.part+'</td>';
            src += '<td>' + i.areacm2.toFixed(1) + 'cm<sup>2</sup></td>';
            src += '<td>' + (i.pressure/1000).toFixed(1) + 'kPa</td>';
            src += '<td>' + i.density.toFixed(1) + '%</td>';
            src += '</tr>';
        });

        src += '</table>';

        src += '</div>'
    }

    $('#infoPanel').html(src);

    if (uiFSM.current == 'modifiers')
        $('#infoPanel').fadeIn('slow');
}

function updateModifierInfo(modi) {
    var src = '';

    if (modi === undefined) {
        $('#infoPanel').fadeOut('slow', function() {
            $('#infoPanel').html('');
        });
        return;
    }

    var g = '';
    src = '<div class="panel-heading">Density Zones</div>';
    src += '<table class="table">';
    src += '<tr> <th>Area</th> <th>Pressure</th> <th>Density</th> </tr>'
    src += '<tr>'
    src += '<td>' + modi.areacm2.toFixed(1) + 'cm<sup>2</sup></td>';
    src += '<td>' + (modi.pressure/1000).toFixed(1) + 'kPa</td>';
    src += '<td>' + modi.density.toFixed(1) + '%</td>';
    src += '</tr>';
    src += '</table>';
    src += '</div>'


    $('#infoPanel').html(src);

    $('#infoPanel').show();
}


function loadScanSTL( data ) {


    // parse geometry
    var geo = parseStl(data);
    if (geo == 'BINARY') {
        // TODO: fix this
        //geo = parseStlBinary(reader.readAsArrayBuffer());
        notify('Unable to read binary STL, please convert to ASCII STL first','error');
    }

    if (geo && geo != 'BINARY') {

        //guif3.open();

        resetFootScan();

        geo.mergeVertices();
        //geo.computeFaceNormals();
        //geo.computeVertexNormals();

        // build mesh
        var mesh = new THREE.Mesh(
            geo,
            //customMaterial.clone()
            new THREE.MeshLambertMaterial({
                overdraw:true,
                color: 0x50a000,
                shading: THREE.FlatShading,
                transparent:true,
                opacity:0.4,
                //wireframe:true,
                side: THREE.DoubleSide
            })
        );
        mesh.renderOrder = 200;

        footObj = mesh;
        footObj.castShadow=true;
        amfFoot.add(mesh);

        updateFootGroup(false);
    }
}


function shapeToDXF(shape) {
    if (shape == undefined) return '';

    var str = "999\nDXF generated by GENSOLE\n";
    str += "  0\nSECTION\n  2\nHEADER\n";
    str += "  0\nENDSEC\n";
    str += "  0\nSECTION\n  2\nTABLES\n";
    str += "  0\nTABLE\n  2\nLTYPE\n  70\n1\n";
    str += "  0\nLTYPE\n  2\nCONTINUOUS\n  3\nSolid Line\n  72\n65\n  73\n0\n  40\n0.0\n";
    str += "  0\nENDTAB\n";
    str += "  0\nTABLE\n  2\nLAYER\n  70\n1\n";
    str += "  0\nLAYER\n  2\nShapeRegion\n  62\n7\n  6\nContinuous\n";
    str += "  0\nENDTAB\n";
    str += "  0\nTABLE\n  2\nSTYLE\n  70\n0\n  0\nENDTAB\n";
    str += "  0\nTABLE\n  2\nVIEW\n  70\n0\n  0\nENDTAB\n";
    str += "  0\nENDSEC\n";
    str += "  0\nSECTION\n  2\nBLOCKS\n";
    str += "  0\nENDSEC\n";
    str += "  0\nSECTION\n  2\nENTITIES\n";

    var points = shape.extractPoints().shape;
    var numpoints_closed = points.length + 1;
    str += "  0\nLWPOLYLINE\n  8\nShapeRegion\n  90\n" + numpoints_closed + "\n  70\n" + 1+ "\n";

    points.map(function(p, index) {
        str += " 10\n" + p.x + "\n 20\n" + p.y + "\n 30\n0.0\n";
    });
    // repeat first point
    str += " 10\n" + points[0].x + "\n 20\n" + points[0].y + "\n 30\n0.0\n";

    str += "  0\nENDSEC\n  0\nEOF\n";
    return str;
};


THREE.Vector3.prototype.toStlString = function(applyTransforms, obj) {
    if (applyTransforms && obj) {
        var v = this.clone().applyMatrix4(obj.matrixWorld);
        return v.x + " " + v.y + " " + v.z;
    } else {
        return this.x + " " + this.y + " " + this.z;
    }
}


function meshToSTL(mesh, applyTransforms) {
    var result = "solid insock\n";

    if (mesh.geometry.faces.length > 0)
    {
        mesh.geometry.faces.map(function(f) {

            result += "facet normal " + f.normal.toStlString(applyTransforms, mesh) + "\nouter loop\n";
            result += "vertex "+ mesh.geometry.vertices[f.a].toStlString(applyTransforms, mesh) +"\n";
            result += "vertex "+ mesh.geometry.vertices[f.b].toStlString(applyTransforms, mesh) +"\n";
            result += "vertex "+ mesh.geometry.vertices[f.c].toStlString(applyTransforms, mesh) +"\n";
            result += "endloop\nendfacet\n";
        });
    }

    result += "endsolid insock\n";
    return result;
}


function exportProfileAsPDF() {
    var size = 'a4';
    var pageHeight = 297;  // less 7mm margin
    var pageWidth  = 210;
    // calculate page size
    if (insock.l > 280) {
        size = 'a3';
        pageHeight = 420;
        pageWidth = 297;
    }

    var doc = new jsPDF('p','mm',size);

    doc.setLineWidth(0.5);
    doc.setDrawColor(0);

    // heading
    doc.setTextColor(128);
    doc.setFontSize(22);
    if (patient.name != '') doc.text(10, 15, 'Patient: '+patient.name);
    doc.setFontSize(16);
    doc.text(10, 28, 'Foot: '+insock.whichFoot);


    // insock shape
    var y = pageHeight - (pageHeight - insock.l)/2;

    var lp = insock.inPoints[0];
    var lp2 = insock.outPoints[0];
    for (var i=1; i<insock.inPoints.length; i++) {
        var p = insock.inPoints[i];
        var p2 = insock.outPoints[i];

        doc.line(lp.x + pageWidth/2, y - lp.y , p.x + pageWidth/2, y - p.y);
        lp = p;


        doc.line(lp2.x + pageWidth/2, y - lp2.y , p2.x + pageWidth/2, y - p2.y);
        lp2 = p2;
    }


    // key dimension lines
    doc.setDrawColor(128,128,128);
    doc.line(pageWidth/2, y , pageWidth/2, y - insock.l);

	// Output as Data URI
	//var uri = doc.output('datauristring');

    //$('#exportLink').attr('href',uri);

    //var win = window.open(uri, '_blank');
    //win.focus();

    // prompt to save PDF
    var fn = insock.whichFoot + ' Shoe Profile.pdf';
    if (patient.name != '') fn = patient.name + ' ' + fn;
    doc.save(fn);
}


/*

 Utilities

*/


function notify(msg, t) {
    if (!t) t = 'success';
    if (t == 'error') t = 'danger';

    $.notify({
        message: msg
    },{
        type: t,
        delay: 3000,
        offset: {
            x: 20,
            y: 70
        },
        animate: {
            enter: 'animated fadeInDown',
            exit: 'animated fadeOutUp'
        }
    });
}


function timeToStr(duration) {
    // takes a duration in seconds, returns nicely formatted
    minutes = parseInt(duration / 60, 10);
    seconds = parseInt(duration % 60, 10);

    minutes = minutes < 10 ? "0" + minutes : minutes;
    seconds = seconds < 10 ? "0" + seconds : seconds;

    return minutes + ":" + seconds;
}


Number.prototype.round = function(places) {
return +(Math.round(this + "e+" + places)  + "e-" + places);
}


if (typeof String.prototype.endsWith !== 'function') {
    String.prototype.endsWith = function(suffix) {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}

if(typeof(String.prototype.trim) === "undefined")
{
    String.prototype.trim = function()
    {
        return String(this).replace(/^\s+|\s+$/g, '');
    };
}



function sleep(milliseconds) {
  var start = new Date().getTime();
  for (var i = 0; i < 1e7; i++) {
    if ((new Date().getTime() - start) > milliseconds){
      break;
    }
  }
}

function sqr(a) {
    return a*a;
}

function clamp(val, min, max){
    return Math.max(min, Math.min(max, val));
}

// a is start value, b is end, p ranges 0-1
function lerp(a,b,p) {
    return a + (b-a)*p;
}

function degToRad(a) {
    return Math.PI * a / 180;
}

function radToDeg(a) {
    return 180 * a / Math.PI;
}
