/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Model } from "@web/model/model";
import { KeepLast } from "@web/core/utils/concurrency";
import {formatDateTime, deserializeDateTime } from "@web/core/l10n/dates";

export class BaseGanttModel extends Model {
    setup(params) {
        this.metaData = {
            ...params,
        };
        this.data = {
            count: 0,
            records: [],
        };
        this.timeFrame = 'Month';
        this.dateStartField = params.dateStartField;
        this.dateStopField = params.dateStopField;
        this.colorField = params.colorField;
        this.taskProgress = params.taskProgress;

        this.keepLast = new KeepLast();
    }
    async load(params) {
        const metaData = {
            ...this.metaData,
            ...params,
        };
        this.data = await this._fetchData(metaData);
        this.metaData = metaData;
    }
    _getFields(metaData) {
        const fields = new Set([
            "name",
            metaData.dateStartField,
            metaData.dateStopField,
        ]);
        if (metaData.parentField) {
            fields.add(metaData.parentField);
        }
        if (metaData.userIdsField) {
            fields.add(metaData.userIdsField);
        }
        if (metaData.colorField) {
            fields.add(metaData.colorField);
        }
        if (metaData.taskProgress) {
            fields.add(metaData.taskProgress);
        }
        return [...fields];
    }
    _buildMetaData(params = {}) {
        return this.metaData;
    }
    async fetchData(params) {
        var data = await this._fetchData(this._buildMetaData(params));
        return data;
    }
    async _fetchData(metaData) {
        var self = this; 
        const data = {
            count: 0,
            records: [],
        }
        const results = await this.keepLast.add(this._fetchRecordData(metaData));        
        if (results && results[0].records){
            const dataSorted = results[0].records.reduce((accumulator, currentValue) => {
                if (currentValue.parent_id && currentValue.parent_id.id) {
                    let item = accumulator.find(x => x.id === currentValue.parent_id.id);
                    let index = accumulator.indexOf(item);
                    index = index !== -1 ? index + 1 : accumulator.length;
                    accumulator.splice(index, 0, currentValue);
                } else {
                    accumulator.push(currentValue);
                }
                return accumulator;
            }, []);
            data.records = self._processData(dataSorted);
        }else{
            data.records = [];
        }
        data.count = results.length;
        return data;
    }
    async _fetchRecordData(metaData){
        const promises = [];
        const fields = this._getFields(metaData);
        const specification = {};
        for (const fieldName of fields) {
            specification[fieldName] = {};
            if (metaData.fields[fieldName] && metaData.fields[fieldName].type){
                if (["many2one", "one2many", "many2many"].includes(metaData.fields[fieldName].type)) {
                    specification[fieldName].fields = { display_name: {} };
                }
            }
        }
        const orderBy = [];
        if (metaData.defaultOrder) {
            orderBy.push(metaData.defaultOrder);
            if (metaData.defaultOrder) {
                orderBy.push("asc");
            }

        }

        var result = await this.orm.webSearchRead(metaData.resModel, metaData.domain, {
            specification: specification,
            limit: metaData.limit,
            offset: metaData.offset,
            order: orderBy.join(" "),
            context: metaData.context,
        })

        promises.push(result);
        return Promise.all(promises);
    }
    _processData(data){
        var self = this;

        if (!data) {
            return;
        }

        var records = [];   
        for (let i = 0; i < data.length; i++) {
            let start = false;
            let stop = false;
            let users_names = false;
            let progress = false;
            
            if (data[i][self.dateStartField]) {
                const date = deserializeDateTime(data[i][self.dateStartField]);
                start = formatDateTime(date, {
                    format: "yyyy-MM-dd HH:mm:ss",
                    numberingSystem: "latn",
                })
            }
            if (data[i][self.dateStopField]) {
                const date = deserializeDateTime(data[i][self.dateStopField]);
                stop = formatDateTime(date, {
                    format: "yyyy-MM-dd HH:mm:ss",
                    numberingSystem: "latn",
                })
            }

            if (data[i]['user_ids']) {
                var names = "";
                var users  = data[i]['user_ids'];
                for (var j = 0, l = users.length; j < l; ++j) {
                    if(j>0){
                        names += ','; 
                    }
                    names += users[j].display_name;
                }
                users_names = names;
            }

            if (data[i][self.taskProgress]) {
                progress = data[i][self.taskProgress];
            }

            let dataTask = {
                id: data[i]['id'].toString(),
                name: data[i]['name'],
                start: start,
                end: stop,
                users_names: users_names,
                progress: progress,
                custom_class: self.getCustomClass(data[i]['color']),
            };

            if (data[i]['parent_id'] && data[i]['parent_id'].id) {
                dataTask['dependencies'] = data[i]['parent_id'].id.toString();
            }

            records.push(dataTask);
        }
        return records;
    }

    getCustomClass(color){
        var self = this;
        var custom_class = 'oe_base_gantt_color_0';
        if (color) {                
            if (color == '0'){
                custom_class = 'oe_base_gantt_color_0';
            }
            if (color == '1'){
                custom_class = 'oe_base_gantt_color_1';
            }
            if (color == '2'){
                custom_class = 'oe_base_gantt_color_2';
            }
            if (color == '3'){
                custom_class = 'oe_base_gantt_color_3';
            }
            if (color == '4'){
                custom_class = 'oe_base_gantt_color_4';
            }
            if (color == '5'){
                custom_class = 'oe_base_gantt_color_5';
            }
            if (color == '6'){
                custom_class = 'oe_base_gantt_color_6';
            }
            if (color == '7'){
                custom_class = 'oe_base_gantt_color_7';
            }
            if (color == '8'){
                custom_class = 'oe_base_gantt_color_8';
            }
            if (color == '9'){
                custom_class = 'oe_base_gantt_color_9';
            }
            if (color == '10'){
                custom_class = 'oe_base_gantt_color_10';
            }
            if (color == '11'){
                custom_class = 'oe_base_gantt_color_11';
            }
        }
        return custom_class;
    }
}
