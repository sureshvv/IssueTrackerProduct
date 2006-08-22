// from http://ejohn.org/projects/flexible-javascript-events/
function addEvent(obj, type, fn) { 
  if (obj.attachEvent) {
    obj["e"+type+fn] = fn;
    obj[type+fn] = function() { obj["e"+type+fn]( window.event ); }
    obj.attachEvent("on"+type, obj[type+fn]);
  } else
    obj.addEventListener(type, fn, false);
    
}

// from http://ejohn.org/projects/flexible-javascript-events/
function removeEvent(obj, type, fn) {
  if (obj.detachEvent) {
    obj.detachEvent("on"+type, obj[type+fn]);
    obj[type+fn] = null;
  } else
    obj.removeEventListener(type, fn, false);
}

function $() {
  var elements = new Array();
  for (var i=0; i < arguments.length; i++) {
    var element = arguments[i];
    if (typeof element == 'string')
      element=document.getElementById(element);
    if (arguments.length == 1) 
      return element;
    elements.push(element);
  }
  return elements;
}
function stripSpaces(x) {
   return x.replace(/^\s+|\s+$/g,'');
}

function econvert(s) {
return s.replace(/%7E/g,'~').replace(/%28/g,'(').replace(/%29/g,')').replace(/%20/g,' ').replace(/_dot_| dot |_\._|\(\.\)/gi, '.').replace(/_at_|~at~/gi, '@');}

function AEHit() {
var sp = document.getElementsByTagName("span");
for (i=0; i< sp.length; i++) 
    if (sp[i].className=="aeh") 
        sp[i].innerHTML = econvert(sp[i].innerHTML);
}


addEvent(window, 'load', AEHit);

function form2querystring(f) {
  var d = '';
  for (i=0;i < f.elements.length;i++) {
    ob = f.elements[i];
    if ((ob.type=='text' || ob.type=='textarea' || ob.type=='hidden') ||
        (ob.type=='radio' && ob.checked)) {
      if (ob.name!='')
        d += ob.name +'='+ escape(ob.value) +'&';
    } else if (ob.type=='select-one') {
      d += ob.name +'='+ escape(ob.options[ob.selectedIndex].value) +'&';
    } else if (ob.type=='select-multiple') {
      for (y=0;y < ob.options.length;y++) 
        if (ob.options[y].selected)
	  d += ob.name +'='+ escape(ob.options[y].value) +'&';
    } else if (ob.type=='checkbox') {
      if (ob.checked) d += ob.name +'=1&';
      else d += ob.name +'=False&';
    }
  }
  return d;
}
function G(p) {
  location.href=p;
}

function checkCaptchaValue(elm, msg, maxlength) {
   var v = stripSpaces(elm.value);
   if (v) {
      if (v.search(/\D/)>-1)
        alert(msg);
      v = v.replace(/\D/g,'');
      if (v.length >= maxlength) 
        v = v.substring(0, maxlength);
      elm.value = v;
   }
}