
function L(x) { // shortcut
   if (window.console && window.console.log)
     window.console.log(x);
}

function saveNote(form, thread_identifier) {
   var public = false;
   $.each(form.public, function(i, e) {
      if (e.checked && e.value=="yes") public = true;
   });
   if (!$(form.comment).val().length) {
      cancelSaveNote(form, thread_identifier);
   }
   
   if (!thread_identifier) thread_identifier = '';

   $.post(ROOT_URL + '/saveIssueNote', {
      issue_identifier:$(form.issue_identifier).val(),
      thread_identifier:thread_identifier,
      comment:$(form.comment).val(), 
      public:public},
          function(result) {
      if (result) alert(result);
      //L(thread_identifier);
      cancelSaveNote(form, thread_identifier);
   });
      
}

function cancelSaveNote(form, thread_identifier) {
   if (thread_identifier)
     $('a.new-note', 'div.thead').qtip('hide');
   else
     $('a.new-note', 'div.ihead').qtip('hide');
}

function _basic_qtip_options(note) {
   var title = note.date; //"Fake title"; // note.title
   if (note.fromname)
     title += " by " + note.fromname;
   var text = note.comment;
   return {
      content: {
         title: {
            text: title
         },
         text:text
      },
      position: {
                  corner: {
                     tooltip: 'rightTop', // Use the corner...
                     target: 'leftBottom' // ...and opposite corner
                  }
               },
      style: {
                  border: {
                     width: 2,
                     radius: 4
                  },
                  padding: 3,
                  textAlign: 'left',
                  tip: true, // Give it a speech bubble tip with automatic corner detection
                  name: 'light' // Style it according to the preset 'cream' style
               }

   };
}
function __show_note(issue_identifier, note) {
   var parent = $('#' + issue_identifier);
   if (note.threadID) {
      // the ID of the div for this followup is going to be the 
      // end of issue_identifier + '__' + note.threadID
      var containerID = issue_identifier.split('__').pop() + '__' + note.threadID;
      var container = $('div.thead', '#' + containerID);
   } else {
      var container = $('div.ihead', parent);
   }
   var link = $('<a href="#"></a>').addClass('old-note').click(function() {
      return false;
   }).append(
             $('<img src="/misc_/IssueTrackerProduct/issuenote.png" border="0"/>').attr('alt',note.title)
             ).qtip(_basic_qtip_options(note));
   
   container.prepend(link);
}


$(function () {
   
   function _qtip_options(target, issue_identifier, thread_identifier) {
      var text = '';
      if (thread_identifier)
         text += '<form action="" onsubmit="saveNote(this, \'' + thread_identifier+ '\'); return false">';
      else
         text += '<form action="" onsubmit="saveNote(this, null); return false">';
      text += '<input type="hidden" name="issue_identifier" value="'+ issue_identifier+'"/>'+
               '<textarea name="comment" rows="5" cols="40"></textarea><br/>'+
               'Public <input type="radio" name="public" value="yes" checked="checked"/>&nbsp;'+
               'Private <input type="radio" name="public" value=""/><br/>'+
               '<input type="submit" value="Save"/> ';
      if (thread_identifier) {
         text += '<a href="#" onclick="cancelSaveNote(this, \'' + thread_identifier+ '\');return false;">Cancel</a> ';
      } else {
         text += '<a href="#" onclick="cancelSaveNote(this, null);return false;">Cancel</a> ';
      }
      text += '</form>';
      
      return {
   
      content: {
         title: {
            text: 'Save a new note',
            button: 'Close'
         },
         text: text
      },
      position: {
         target: target, // Position it via the document body...
         corner: 'right' // ...at the center of the viewport
      },
      show: {
         when: 'click', // Show it on click
         solo: true // And hide all other tooltips
      },
      hide: false,
      style: {
         width: { max: 350 },
         padding: '14px',
         border: {
            width: 9,
            radius: 9,
            color: '#666666'
         },
         name: 'light'
      },
      api: {
         beforeShow: function() {
            // Fade in the modal "blanket" using the defined show speed
            $('#qtip-blanket').fadeIn(this.options.show.effect.length);
         },
         onShow: function() {
            $('textarea[name="comment"]')[0].focus();
         },
         beforeHide: function() {
            // Fade out the modal "blanket" using the defined hide speed
            $('#qtip-blanket').fadeOut(this.options.hide.effect.length);
         }
      }
      };
   }

   var issue_identifier;
   var thread_identifier;
   
   $('div.issue').each(function() {
      
      issue_identifier = $(this).attr('id');
      $('div.ihead', this).prepend($('<a href="#"></a>').click(function() {
         return false;
      }).addClass('new-note')
          .append($('<img>')
                   .attr('src','/misc_/IssueTrackerProduct/new-issuenote.png')
                   .attr('border','0')
                  .attr('alt','New note')
		  ).qtip(_qtip_options($(this), issue_identifier, null))
        );
      
      $('div.threadbox').each(function() {
         thread_identifier = $(this).attr('id');
        $('div.thead', this).prepend($('<a href="#"></a>').click(function() {
           return false;
        }).addClass('new-note')
            .append($('<img>')
                     .attr('src','/misc_/IssueTrackerProduct/new-issuenote.png')
                     .attr('border','0')
                    .attr('alt','New note')
  		  ).qtip(_qtip_options($(this), issue_identifier, thread_identifier))
          );
     });
      
   });

   $('div.issue').each(function() {
      var issue_identifier = $(this).attr('id');
      $.getJSON(ROOT_URL + '/getIssueNotes_json', {issue_identifier:issue_identifier}, function(notes) {
	 $.each(notes, function(i, note) {
	    __show_note(issue_identifier, note);
	 });
      });
   });
      
   
   // Create the modal backdrop on document load so all modal tooltips can use it
   $('<div id="qtip-blanket">')
      .css({
         position: 'absolute',
         top: $(document).scrollTop(), // Use document scrollTop so it's on-screen even if the window is scrolled
         left: 0,
         height: $(document).height(), // Span the full document height...
         width: '100%', // ...and full width

         opacity: 0.7, // Make it slightly transparent
         backgroundColor: 'black',
         zIndex: 5000  // Make sure the zIndex is below 6000 to keep it below tooltips!
      })
      .appendTo(document.body) // Append to the document body
      .hide(); // Hide it initially
   
   
});