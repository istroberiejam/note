(function(root){
  const KEY='margin-notebooks-v1';
  const SUBJECTS=['Clinical Microscopy','Clinical Bacteriology','Clinical Chemistry','Clinical Hematology 1'];
  const blank=title=>({title,concepts:[],references:[],lectures:[],sources:[],quiz:'',exam:''});
  function open(storage,id=()=>crypto.randomUUID()){
    const raw=storage.getItem(KEY);let state;
    if(raw){state=JSON.parse(raw);if(state.version!==1||!Array.isArray(state.notebooks)||!state.notebooks.length)throw Error('Saved notebooks could not be loaded. Your stored data has not been replaced.');}
    else{
      state={version:1,activeId:'',notebooks:SUBJECTS.map(name=>({id:id(),name,project:blank(name)}))};
      const legacy=storage.getItem('margin-notebook');
      if(legacy){const project=JSON.parse(legacy);if(!project||!Array.isArray(project.concepts))throw Error('Existing notes could not be loaded. Your stored data has not been replaced.');const previous={id:id(),name:'Existing notebook',project};state.notebooks.unshift(previous);}
      state.activeId=state.notebooks[0].id;
    }
    function persist(){storage.setItem(KEY,JSON.stringify(state));}
    function get(notebookId=state.activeId){const n=state.notebooks.find(n=>n.id===notebookId);if(!n)throw Error('Notebook not found.');return n;}
    if(!state.notebooks.some(n=>n.id===state.activeId))state.activeId=state.notebooks[0].id;
    return {state,get,persist,select(notebookId){get(notebookId);state.activeId=notebookId;persist();return get();},add(name){name=name.trim();if(!name||name.length>100)throw Error('Enter a subject name between 1 and 100 characters.');if(state.notebooks.some(n=>n.name.toLowerCase()===name.toLowerCase()))throw Error('A notebook with this name already exists.');const n={id:id(),name,project:blank(name)};state.notebooks.push(n);state.activeId=n.id;persist();return n;},clear(){get().project=blank(get().name);persist();return get();}};
  }
  const exported={open,blank,SUBJECTS,KEY};if(typeof module!=='undefined'&&module.exports)module.exports=exported;else root.MarginNotebooks=exported;
})(globalThis);
